"""Optional, certificate-pinned LG Signage web manager (verified on UH5F-H).

This is an internal vendor interface, not the consumer webOS/SSAP API. No
credential, cookie, message or media URL is included in errors or diagnostics.
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid

import aiohttp
from yarl import URL


class LGWebError(Exception):
    """Sanitized LG web-manager failure."""


def normalize_fingerprint(value: str) -> str:
    value = value.replace(":", "").replace(" ", "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("A SHA-256 certificate fingerprint is required")
    return value


async def _read_limited(response, limit=262144):
    """Read complete, possibly fragmented responses with a hard memory limit."""
    chunks = bytearray()
    async for chunk in response.content.iter_chunked(65536):
        chunks.extend(chunk)
        if len(chunks) > limit:
            raise LGWebError("LG web response exceeds size limit")
    return bytes(chunks)


class LGWebManager:
    """One private cookie jar, serialized requests and no replay of mutations."""

    def __init__(self, host: str, password: str, fingerprint: str):
        self._host = host
        self._password = password
        self._ssl = aiohttp.Fingerprint(
            bytes.fromhex(normalize_fingerprint(fingerprint))
        )
        self._session = None
        self._lock = asyncio.Lock()
        self._authenticated = False

    def _url(self, port: int, path: str) -> URL:
        return URL.build(scheme="https", host=self._host, port=port, path=path)

    async def async_close(self):
        if self._session:
            await self._session.close()
            self._session = None
        self._authenticated = False

    async def _json(self, method, path, *, params=None, data=None, body=None):
        if self._session is None:
            self._session = aiohttp.ClientSession(
                cookie_jar=aiohttp.CookieJar(unsafe=True),
                timeout=aiohttp.ClientTimeout(total=20),
            )
        try:
            async with self._session.request(
                method,
                self._url(3777, path),
                params={"reqParam": json.dumps(params)} if params is not None else None,
                data=data,
                json=body,
                ssl=self._ssl,
                allow_redirects=False,
            ) as response:
                if response.status != 200:
                    raise LGWebError(
                        "LG web request rejected; check login and certificate"
                    )
                raw = await _read_limited(response)
                result = json.loads(raw)
                if result.get("status") != 200:
                    raise LGWebError("LG web request failed")
                return result.get("data")
        except (aiohttp.ClientError, TimeoutError, ValueError, AttributeError):
            raise LGWebError("LG web connection or response failed") from None

    async def _login(self):
        if self._authenticated:
            try:
                if await self._json("GET", "/login/checkLoginStatus") is True:
                    return
            except LGWebError:
                self._authenticated = False
        self._authenticated = False
        # The LG web login itself exposes this accessible CAPTCHA representation.
        # No authentication requirement is skipped or disabled.
        if self._session is None:
            await self._json("GET", "/login/checkLoginStatus")
        try:
            async with self._session.get(
                self._url(3777, "/login/captcha"),
                ssl=self._ssl,
                allow_redirects=False,
            ) as response:
                if response.status != 200:
                    raise LGWebError("LG login challenge unavailable")
                await _read_limited(response)
            challenge = await self._json("GET", "/login/captchaText")
            if not isinstance(challenge, dict) or not isinstance(
                challenge.get("text"), str
            ):
                raise LGWebError("LG login challenge unavailable")
            result = await self._json(
                "POST",
                "/login/login",
                body={
                    "passwd": self._password,
                    "captcha": challenge["text"],
                },
            )
            if not isinstance(result, dict) or result.get("result") is not True:
                raise LGWebError(
                    "LG web login rejected; verify the Mobile URL password"
                )
            self._authenticated = True
        except (aiohttp.ClientError, TimeoutError):
            raise LGWebError("LG web login connection failed") from None

    async def _api(self, command, event, **params):
        """One bounded Engine.IO 3 / Socket.IO 2 request; mutations never retry."""
        await self._login()
        try:
            async with asyncio.timeout(12):
                async with self._session.ws_connect(
                    self._url(3737, "/socket.io/").with_query(
                        EIO="3", transport="websocket"
                    ),
                    ssl=self._ssl,
                    max_msg_size=262144,
                ) as ws:
                    opened = False
                    while True:
                        message = await ws.receive()
                        if message.type != aiohttp.WSMsgType.TEXT:
                            raise LGWebError("LG control connection closed")
                        packet = message.data
                        if packet.startswith("0"):
                            opened = True
                        elif packet == "40" and opened:
                            break
                        elif packet.startswith("44"):
                            raise LGWebError("LG control login rejected")
                    await ws.send_str(
                        "42"
                        + json.dumps(
                            ["api", {"command": command, "eventID": 1, **params}]
                        )
                    )
                    while True:
                        message = await ws.receive()
                        if message.type != aiohttp.WSMsgType.TEXT:
                            raise LGWebError("LG control connection closed")
                        packet = message.data
                        if packet.startswith("2"):
                            await ws.send_str("3" + packet[1:])
                        elif packet.startswith("42"):
                            reply = json.loads(packet[2:])
                            if not isinstance(reply, list) or len(reply) < 2:
                                continue
                            if reply[0] == "error":
                                self._authenticated = False
                                raise LGWebError("LG control session expired")
                            if event == "toast" and reply[0] == "return":
                                value = reply[1]
                                if (
                                    isinstance(value, dict)
                                    and value.get("from") == "toast"
                                ):
                                    if value.get("result") is not True:
                                        raise LGWebError("LG rejected the toast")
                                    return value
                            elif reply[0] == event + "1":
                                value = reply[1]
                                if event == "capture" and isinstance(value, str):
                                    return value
                                if (
                                    not isinstance(value, dict)
                                    or value.get("returnValue") is False
                                ):
                                    raise LGWebError("LG rejected the control request")
                                return value
        except (aiohttp.ClientError, TimeoutError, ValueError):
            raise LGWebError("LG control request failed; it was not replayed") from None

    async def async_toast(self, message: str):
        if not message.strip() or len(message) > 1000:
            raise LGWebError("Toast must contain 1–1000 characters")
        async with self._lock:
            await self._api("sendToast", "toast", message=message)

    async def async_foreground_app(self) -> str | None:
        async with self._lock:
            result = await self._api("getForegroundAppInfo", "getForegroundAppInfo")
            return result.get("appId")

    async def async_upload_image(self, image: bytes) -> dict:
        if not 0 < len(image) <= 5 * 1024 * 1024:
            raise LGWebError("Image must be at most 5 MiB")
        if image.startswith(b"\x89PNG\r\n\x1a\n"):
            suffix, content_type = ".png", "image/png"
        elif image.startswith(b"\xff\xd8\xff"):
            suffix, content_type = ".jpg", "image/jpeg"
        else:
            raise LGWebError("Native images must be PNG or JPEG")
        name = f"ha_lg_{uuid.uuid4().hex}{suffix}"
        form = aiohttp.FormData()
        form.add_field("file", image, filename=name, content_type=content_type)
        async with self._lock:
            await self._login()
            result = await self._json("POST", "/file/contentManager", data=form)
            try:
                uploaded = result["data"]["files"]["file"]
                path = uploaded["path"]
                if (
                    result.get("result") is not True
                    or path != f"/mnt/lg/appstore/signage/{name}"
                ):
                    raise LGWebError("LG returned an unexpected upload location")
            except (TypeError, KeyError):
                raise LGWebError("LG did not confirm the image upload") from None
            return {"name": name, "path": path}

    async def async_play_image(self, asset: dict):
        self._validate_asset(asset)
        async with self._lock:
            await self._login()
            result = await self._json(
                "PUT",
                "/content/play/dsmp",
                params={
                    "id": "com.webos.app.dsmp",
                    "params": {"type": "image", "src": asset["path"]},
                },
            )
            if (
                not isinstance(result, dict)
                or result.get("payload", {}).get("returnValue") is not True
            ):
                raise LGWebError("LG did not confirm image playback")
        # ACK means launch accepted. Verify that the native player really entered foreground.
        for _ in range(5):
            if await self.async_foreground_app() == "com.webos.app.dsmp":
                return
            await asyncio.sleep(0.4)
        raise LGWebError("LG native player did not enter foreground")

    @staticmethod
    def _validate_asset(asset):
        name = asset.get("name", "")
        if (
            not re.fullmatch(r"ha_lg_[0-9a-f]{32}\.(?:png|jpg)", name)
            or asset.get("path") != f"/mnt/lg/appstore/signage/{name}"
        ):
            raise LGWebError("Refusing to operate on a non-owned media path")

    async def async_delete_image(self, asset: dict):
        self._validate_asset(asset)
        async with self._lock:
            await self._login()
            result = await self._json(
                "DELETE",
                "/content",
                params={
                    "path": [
                        {
                            "deviceId": "INTERNAL_STORAGE_SIGNAGE",
                            "subDeviceId": "",
                            "itemPath": asset["path"],
                            "type": "image",
                        }
                    ]
                },
            )
            if (
                not isinstance(result, dict)
                or result.get("payload", {}).get("returnValue") is not True
            ):
                raise LGWebError("LG could not delete the temporary image")

    async def async_capture(self, height: int = 720) -> bytes:
        """Capture a real panel frame; download only the returned same-device path."""
        if height not in (360, 720, 1080):
            raise LGWebError("Unsupported capture resolution")
        async with self._lock:
            path = await self._api("capture", "capture", height=height)
            if not isinstance(path, str) or not re.fullmatch(
                r"/tmp/capture[0-9]+\.jpg", path
            ):
                raise LGWebError("LG did not return a valid capture path")
            try:
                # Capture paths are served by Control Manager, NOT Content Manager.
                async with self._session.get(
                    self._url(3737, path),
                    ssl=self._ssl,
                    allow_redirects=False,
                ) as response:
                    if response.status != 200:
                        raise LGWebError("LG screenshot is unavailable")
                    image = await _read_limited(response, 5 * 1024 * 1024)
                    if not image.startswith(b"\xff\xd8\xff") or not image.endswith(
                        b"\xff\xd9"
                    ):
                        raise LGWebError("LG returned an invalid JPEG screenshot")
                    return image
            except (aiohttp.ClientError, TimeoutError):
                raise LGWebError("LG screenshot download failed") from None
