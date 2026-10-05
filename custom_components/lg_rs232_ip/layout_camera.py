"""On-demand camera access for paired displays; no background camera polling."""

import asyncio
from collections import OrderedDict
import time

from homeassistant.components import camera
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .layout_media import prepare_covers


class LayoutCamera:
    def __init__(self, hass):
        self.hass = hass
        self._cache = OrderedDict()
        self._tasks = {}
        self._slots = asyncio.Semaphore(2)
        self._closed = False

    def allowed(self, entity_id):
        state = self.hass.states.get(entity_id)
        record = er.async_get(self.hass).async_get(entity_id)
        return bool(
            state
            and state.domain == "camera"
            and state.state not in ("unavailable", "unknown", "off")
            # Never feed this integration's display preview back into a display.
            and not (record and record.platform == DOMAIN)
        )

    async def async_get(self, entity_id, kind):
        if self._closed or not self.allowed(entity_id):
            return None
        key = (entity_id, kind)
        cached = self._cache.get(key)
        if cached and time.monotonic() < cached[0]:
            return cached[1]
        if key not in self._tasks:
            if len(self._tasks) >= 4:
                return None
            self._tasks[key] = asyncio.create_task(self._fetch(key))
        return await asyncio.shield(self._tasks[key])

    async def _fetch(self, key):
        entity_id, kind = key
        value = None
        try:
            async with asyncio.timeout(10), self._slots:
                if kind == "stream":
                    url = await camera.async_request_stream(self.hass, entity_id, "hls")
                    # HA owns the stream. Never reveal a camera's RTSP credentials.
                    if isinstance(url, str) and url.startswith("/api/hls/"):
                        value = url
                else:
                    image = await camera.async_get_image(
                        self.hass, entity_id, width=1280, height=720
                    )
                    images = await self.hass.async_add_executor_job(
                        prepare_covers, image.content, (1280,)
                    )
                    value = images[1280]
        except Exception:
            # An unavailable/unsupported stream falls back to snapshots in the app.
            # Errors may contain camera credentials; do not log their text.
            pass
        finally:
            self._tasks.pop(key, None)
        self._cache[key] = (time.monotonic() + (60 if kind == "stream" else 1), value)
        self._cache.move_to_end(key)
        while len(self._cache) > 8:
            self._cache.popitem(last=False)
        return value

    async def async_close(self):
        self._closed = True
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        self._cache.clear()
