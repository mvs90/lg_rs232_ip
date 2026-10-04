"""Demand-driven, scoped album artwork through HA's existing media entity API."""

import asyncio
from collections import OrderedDict
from hashlib import sha256
import hmac
from io import BytesIO
import json
import secrets
import time

from PIL import Image, ImageOps

MAX_BYTES = 5 * 1024 * 1024


def prepare_cover(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Invalid artwork size")
    with Image.open(BytesIO(raw)) as image:
        if (
            image.format not in {"JPEG", "PNG", "WEBP", "GIF"}
            or image.width * image.height > 20_000_000
        ):
            raise ValueError("Unsupported artwork")
        image = ImageOps.exif_transpose(image)
        image.thumbnail((640, 640), Image.Resampling.LANCZOS)
        rgba = image.convert("RGBA")
        rgb = Image.new("RGB", image.size, "#172535")
        rgb.paste(rgba, mask=rgba.getchannel("A"))
        out = BytesIO()
        rgb.save(out, format="JPEG", quality=85)
        return out.getvalue()


class LayoutMedia:
    def __init__(self, hass):
        self.hass = hass
        self._salt = secrets.token_bytes(32)
        self._cache = OrderedDict()
        self._tasks = {}
        self._semaphore = asyncio.Semaphore(2)
        self._closed = False

    def key(self, entity_id):
        state = self.hass.states.get(entity_id)
        if (
            not state
            or state.domain != "media_player"
            or state.state in ("off", "standby", "unknown", "unavailable")
        ):
            return None
        attrs = state.attributes
        if not attrs.get("entity_picture"):
            return None
        source = [entity_id] + [
            attrs.get(k)
            for k in (
                "entity_picture",
                "media_content_id",
                "media_title",
                "media_artist",
                "media_album_name",
            )
        ]
        return hmac.new(
            self._salt, json.dumps(source, default=str).encode(), sha256
        ).hexdigest()

    async def async_image(self, entity_id, key):
        if self._closed or not key or key != self.key(entity_id):
            return None
        cached = self._cache.get(entity_id)
        if (
            cached
            and cached[0] == key
            and (cached[1] is not None or time.monotonic() - cached[2] < 30)
        ):
            self._cache.move_to_end(entity_id)
            return cached[1]
        # One fetch per player across the LG and editor. A disconnected client
        # must not cancel another viewer's shared request.
        if entity_id not in self._tasks:
            if len(self._tasks) >= 32:
                return None
            self._tasks[entity_id] = asyncio.create_task(self._fetch(entity_id, key))
        await asyncio.shield(self._tasks[entity_id])
        cached = self._cache.get(entity_id)
        if key == self.key(entity_id) and (not cached or cached[0] != key):
            return await self.async_image(entity_id, key)
        return (
            cached[1]
            if cached and cached[0] == key and key == self.key(entity_id)
            else None
        )

    async def _fetch(self, entity_id, key):
        data = None
        try:
            async with asyncio.timeout(8):
                async with self._semaphore:
                    component = self.hass.data.get("media_player")
                    player = component.get_entity(entity_id) if component else None
                    if player:
                        raw, _ = await player.async_get_media_image()
                        if raw:
                            data = await self.hass.async_add_executor_job(
                                prepare_cover, raw
                            )
        except Exception:
            data = None
        finally:
            if not self._closed and key == self.key(entity_id):
                self._cache[entity_id] = (key, data, time.monotonic())
                self._cache.move_to_end(entity_id)
                while (
                    len(self._cache) > 32
                    or sum(len(row[1] or b"") for row in self._cache.values())
                    > 8 * 1024 * 1024
                ):
                    self._cache.popitem(last=False)
            self._tasks.pop(entity_id, None)

    async def async_close(self):
        self._closed = True
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._cache.clear()
