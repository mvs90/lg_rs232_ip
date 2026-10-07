"""Optional LG Signage web manager with certificate verification by default (verified on UH5F-H).

This is an internal vendor interface, not the consumer webOS/SSAP API. No
credential, cookie, message or media URL is included in errors or diagnostics.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import ssl
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


async def async_read_certificate_fingerprint(host: str) -> str:
    """Enroll the certificate presented at setup, without sending credentials."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    try:
        async with asyncio.timeout(10):
            _, writer = await asyncio.open_connection(
                host, 3777, ssl=context, server_hostname=host, ssl_handshake_timeout=5
            )
            try:
                certificate = writer.get_extra_info("ssl_object").getpeercert(
                    binary_form=True
                )
                if not certificate:
                    raise LGWebError("LG did not provide an HTTPS certificate")
                return hashlib.sha256(certificate).hexdigest()
            finally:
                writer.close()
                await writer.wait_closed()
    except (OSError, TimeoutError, AttributeError):
        raise LGWebError("Cannot read the LG HTTPS certificate") from None


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

    def __init__(
        self,
        host: str,
        password: str,
        fingerprint: str = "",
        url_store=None,
        *,
        verify_certificate: bool = True,
    ):
        self._url_store = url_store
        self._host = host
        self._password = password
        self._ssl = (
            aiohttp.Fingerprint(bytes.fromhex(normalize_fingerprint(fingerprint)))
            if verify_certificate
            else False
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
                timeout=aiohttp.ClientTimeout(
                    total=120 if path == "/file/contentManager" else 20
                ),
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
                    if event is None:
                        return None
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
                                if event in {"ntp", "setContinent", "setCountry", "setCity", "setDstOnOff"} and value is True:
                                    return {"returnValue": True}
                                if event in {"capture", "signageName"} and isinstance(value, str):
                                    return value
                                if event in {"getCountryList", "getCityList"} and isinstance(value, list):
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

    async def async_get_display_settings(self):
        """Read only the public configuration allowlist; never return credentials."""
        from .system_settings import SYSTEM_KEYS, valid_settings

        async with self._lock:
            values = await self._api(
                "getSystemSettings", "systemSettings",
                category="commercial", keys=[key for key in SYSTEM_KEYS if key not in {"signageSetId", "signageName"}],
            )
            # getSetID is the controller's public readback, not a guessed DB key.
            try:
                address = await self._api("getSetID", "getSetID")
            except LGWebError:
                address = {}
            if isinstance(values, dict):
                values["signageSetId"] = address.get("setId")
                try:
                    values["signageName"] = await self._api("getSignageName", "signageName")
                except LGWebError:
                    values.pop("signageName", None)
        return valid_settings(values)

    async def async_get_maintenance_settings(self):
        """Clock and ISM values from the display's actual configuration service."""
        from .maintenance import MAINTENANCE_KEYS, normalize_settings

        async with self._lock:
            values = await self._api("getSystemSettings", "systemSettings", category="commercial", keys=list(MAINTENANCE_KEYS))
            clock = {}
            for key, command, event in (
                ("clock_auto", "getNTPStatus", "ntpStatus"),
                ("clock", "getCurrentTime", "currentTime"),
                ("timezone", "getTimeZone", "getTimeZone"),
                ("dst", "getDSTInfo", "getDSTInfo"),
            ):
                try:
                    clock[key] = await self._api(command, event)
                except LGWebError:
                    pass
        return normalize_settings(values, clock)

    async def async_get_native_schedules(self):
        from .native_schedules import SCHEDULE_KEYS

        async with self._lock:
            return await self._api("getSystemSettings", "systemSettings", category="commercial", keys=SCHEDULE_KEYS)

    async def async_get_picture_options(self):
        """Read the active input/preset through LG's picture-specific API."""
        from .picture_settings import NATIVE_KEYS

        async with self._lock:
            return await self._api("getPictureDBVal", "pictureDB", keys=NATIVE_KEYS)

    async def async_write_picture_option(self, key, value, mode):
        from .picture_settings import NATIVE_OPTIONS, NATIVE_NUMBERS, native_options

        raw = NATIVE_OPTIONS[key][0] if key in NATIVE_OPTIONS else NATIVE_NUMBERS.get(key)
        if raw is None or key not in native_options({
            raw: value, "pictureMode": mode,
            "pictureModeSettingsActive": "true", "pictureControlLimitation": "false",
        }):
            raise LGWebError("Unsupported picture parameter")
        async with self._lock:
            await self._api("setPictureDBVal", None, settings={
                raw: value, "pictureSettingModified": {mode: True},
            }, **{"from": raw})

    async def async_write_maintenance_settings(self, settings, *, manual_dst=None):
        """Allowlisted atomic commercial writes, or dedicated clock commands."""
        from .maintenance import validate_changes

        settings = validate_changes(settings)
        async with self._lock:
            if "clock_auto" in settings:
                if settings["clock_auto"] and manual_dst is not None:
                    if manual_dst.get("dstMode") == "on":
                        try:
                            await self._api("setDstOnOff", "setDstOnOff", dstOnOff="off")
                        except LGWebError:
                            pass
                        if (await self._api("getDSTInfo", "getDSTInfo")).get("dstMode") != "off":
                            raise LGWebError("Disable manual DST before enabling automatic time")
                await self._api("setNTPStatus", "ntp", useNTP=settings["clock_auto"])
            elif "clock" in settings:
                value = settings["clock"]
                # LG calls this field utc, but its own UI passes local components.
                # This setter has no ACK event on UH5F; caller verifies a new read.
                await self._api("setCurrentTime", None, utc={key: value.strftime(fmt) for key, fmt in (
                    ("year", "%Y"), ("month", "%m"), ("day", "%d"), ("hour", "%H"), ("minute", "%M"))})
            else:
                await self._api("setSystemSettings", "setSystemSettings", category="commercial", settings=settings, shouldCallback=True)

    async def async_write_display_setting(self, key, value):
        """Single validated mutation; caller verifies fresh readback, never replays."""
        from .system_settings import validate_setting

        try:
            value = validate_setting(key, value)
        except ValueError as err:
            raise LGWebError(str(err)) from None
        async with self._lock:
            if key == "signageName":
                # The actual Signage/network name has its own setter; the
                # similarly named commercial DB value is not authoritative.
                await self._api("setSignageName", None, signageName=value)
                return
            # option.setId controls RS232; commercial.signageSetId is a separate
            # value and must never be mistaken for the actual controller address.
            category = "option" if key == "signageSetId" else "commercial"
            settings = {"setId": int(value)} if key == "signageSetId" else {key: value}
            await self._api(
                "setSystemSettings", "setSystemSettings", category=category,
                settings=settings, shouldCallback=True,
            )

    async def async_foreground_app(self) -> str | None:
        async with self._lock:
            result = await self._api("getForegroundAppInfo", "getForegroundAppInfo")
            return result.get("appId")

    async def async_launch_app(self, app_id):
        """Only the SI launcher and HDMI inputs; no arbitrary app/service dispatch."""
        if app_id not in {
            "commercial.signage.signageapplauncher",
            *(f"com.webos.app.hdmi{i}" for i in range(1, 5)),
        }:
            raise LGWebError("Unsupported display app")
        async with self._lock:
            await self._api("setInputSouce", "setInputSouce", appId=app_id)
        for _ in range(10):
            if await self.async_foreground_app() == app_id:
                return
            await asyncio.sleep(0.4)
        raise LGWebError("Display app launch was not confirmed")

    @staticmethod
    def validate_si_settings(settings):
        keys = {
            "serverIpPort",
            "siServerIp",
            "secureConnection",
            "appLaunchMode",
            "fqdnAddr",
            "fqdnMode",
            "appType",
        }
        if not isinstance(settings, dict) or not keys <= settings.keys():
            raise LGWebError("Cannot read complete SI settings")
        result = {key: settings[key] for key in keys}
        if (
            any(not isinstance(value, str) for value in result.values())
            or result["secureConnection"] not in {"on", "off"}
            or result["fqdnMode"] not in {"on", "off"}
            or result["appLaunchMode"] not in {"none", "local", "remote", "usb"}
            or result["appType"] not in {"zip", "ipk"}
            or not result["serverIpPort"].isdigit()
            or not 0 <= int(result["serverIpPort"]) <= 65535
            or len(result["fqdnAddr"]) > 2048
            or len(result["siServerIp"]) > 255
        ):
            raise LGWebError("Unsupported SI settings")
        return result

    async def async_get_si_settings(self):
        async with self._lock:
            value = await self._api(
                "getSystemSettings",
                "systemSettings",
                category="commercial",
                keys=[
                    "serverIpPort",
                    "siServerIp",
                    "secureConnection",
                    "appLaunchMode",
                    "fqdnAddr",
                    "fqdnMode",
                    "appType",
                ],
            )
        return self.validate_si_settings(value)

    async def async_set_si_settings(self, settings):
        settings = self.validate_si_settings(settings)
        async with self._lock:
            await self._api(
                "setSystemSettings",
                "setSystemSettings",
                category="commercial",
                settings=settings,
                shouldCallback=True,
            )
        if await self.async_get_si_settings() != settings:
            raise LGWebError("SI setting change was not confirmed")

    async def async_upload_image(self, image: bytes) -> dict:
        if not 0 < len(image) <= 5 * 1024 * 1024:
            raise LGWebError("Image must be at most 5 MiB")
        if image.startswith(b"\x89PNG\r\n\x1a\n"):
            suffix, content_type = ".png", "image/png"
        elif image.startswith(b"\xff\xd8\xff"):
            suffix, content_type = ".jpg", "image/jpeg"
        else:
            raise LGWebError("Native images must be PNG or JPEG")
        return await self._async_upload_media(image, suffix, content_type)

    async def async_upload_video(self, video: bytes) -> dict:
        if not 12 <= len(video) <= 50 * 1024 * 1024 or video[4:8] != b"ftyp":
            raise LGWebError("Native videos must be MP4 files up to 50 MiB")
        return await self._async_upload_media(video, ".mp4", "video/mp4")

    async def _async_upload_media(self, content, suffix, content_type):
        name = f"ha_lg_{uuid.uuid4().hex}{suffix}"
        form = aiohttp.FormData()
        form.add_field("file", content, filename=name, content_type=content_type)
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
                raise LGWebError("LG did not confirm the media upload") from None
            return {"name": name, "path": path}

    async def async_play_image(self, asset: dict):
        self._validate_asset(asset)
        await self._async_launch_native("image", asset["path"])

    async def async_play_video(self, asset):
        self._validate_asset(asset)
        await self._async_launch_native("video", asset["path"])

    async def _async_launch_native(self, media_type, source):
        async with self._lock:
            await self._login()
            result = await self._json(
                "PUT",
                "/content/play/dsmp",
                params={
                    "id": "com.webos.app.dsmp",
                    "params": {"type": media_type, "src": source},
                },
            )
            if (
                not isinstance(result, dict)
                or result.get("payload", {}).get("returnValue") is not True
            ):
                raise LGWebError("LG did not confirm media playback")
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
            not re.fullmatch(r"ha_lg_[0-9a-f]{32}\.(?:png|jpg|mp4)", name)
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
                            "type": "video"
                            if asset["name"].endswith(".mp4")
                            else "image",
                        }
                    ]
                },
            )
            if (
                not isinstance(result, dict)
                or result.get("payload", {}).get("returnValue") is not True
            ):
                raise LGWebError("LG could not delete the temporary media")

    @staticmethod
    def validate_url(value):
        try:
            url = URL(value)
            if (
                url.scheme not in {"http", "https"}
                or not url.host
                or url.user is not None
            ):
                raise ValueError
            if len(value) > 4096 or any(ord(c) < 32 for c in value):
                raise ValueError
            return str(url)
        except (ValueError, TypeError):
            raise LGWebError(
                "Use an HTTP(S) URL without embedded credentials"
            ) from None

    async def async_save_url_restore(self, previous, temporary):
        if self._url_store is not None:
            await self._url_store.async_save(
                {"previous": previous, "temporary": temporary}
            )

    async def async_clear_url_restore(self):
        if self._url_store is not None:
            await self._url_store.async_remove()

    async def async_recover_url_settings(self):
        """Recover an interrupted URL change only if its value is still ours."""
        if self._url_store is None:
            return
        saved = await self._url_store.async_load()
        if saved is None:
            return
        if await self.async_get_url_settings() == saved["temporary"]:
            await self.async_set_url_settings(saved["previous"])
        await self.async_clear_url_restore()

    async def async_get_url_settings(self):
        async with self._lock:
            result = await self._api("getPlayViaUrl", "getPlayViaUrl")
            if result.get("playViaUrlMode") not in {"on", "off"} or not isinstance(
                result.get("playViaUrl"), str
            ):
                raise LGWebError("Cannot read LG URL loader configuration")
            return {key: result[key] for key in ("playViaUrlMode", "playViaUrl")}

    async def async_set_url_settings(self, settings):
        # This firmware sends no setter callback. Verify with readback, never replay.
        async with self._lock:
            await self._api("setPlayViaUrl", None, **settings)
        for _ in range(5):
            if await self.async_get_url_settings() == settings:
                return
            await asyncio.sleep(0.2)
        raise LGWebError("LG URL loader change was not confirmed")

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
