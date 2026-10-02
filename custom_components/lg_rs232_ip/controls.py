"""Display-only native presentation queue and policy."""

import asyncio
import logging
from collections import deque
from homeassistant.components import media_source
from homeassistant.components.media_player import async_process_play_media_url
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util
from .native_presentations import NativePresentations

_LOGGER = logging.getLogger(__name__)


def in_quiet_hours(start: str, end: str) -> bool:
    """Use Home Assistant's local timezone, including overnight ranges."""
    now = dt_util.now().time()
    first, last = dt_util.parse_time(start), dt_util.parse_time(end)
    if first is None or last is None or first == last:
        return False
    return first <= now < last if first < last else now >= first or now < last


class NativeControls(NativePresentations):
    def _init_controls(self):
        self._control_lock = asyncio.Lock()
        self._presentation_task = None
        self._presentation_active = False
        self._presentation_queue = deque()
        self._presentation_error = None

    async def _async_resolve_media(self, media_id, media_type, target):
        if media_source.is_media_source_id(media_id):
            item = await media_source.async_resolve_media(self.hass, media_id, target)
            media_id, media_type = item.url, item.mime_type
        # Deep links are passed through. Local HA paths/HTTP media get usable URLs.
        if media_id.startswith(("/", "http://", "https://")):
            media_id = async_process_play_media_url(self.hass, media_id)
        return media_id, media_type

    def _check_presentation_policy(self, priority):
        options = self._config_entry.options
        if (
            priority != "urgent"
            and options.get("quiet_hours_enabled", False)
            and in_quiet_hours(
                options.get("quiet_hours_start", "22:00"),
                options.get("quiet_hours_end", "07:00"),
            )
        ):
            raise ServiceValidationError("Presentation blocked by quiet hours")

    async def _enqueue_presentation(self, request):
        async with self._control_lock:
            await self._enqueue_presentation_locked(request)

    async def _enqueue_presentation_locked(self, request):
        if self.external_owner is not None:
            raise HomeAssistantError(
                "An external AV presentation currently owns the display"
            )
        self._check_presentation_policy(request["priority"])
        if self._ha_stopping:
            raise HomeAssistantError("Integration is stopping")
        if len(self._presentation_queue) >= 10:
            raise ServiceValidationError("Presentation queue is full (10 requests)")
        if request["priority"] == "urgent":
            self._presentation_queue.appendleft(request)
        else:
            self._presentation_queue.append(request)
        if self._presentation_task is None or self._presentation_task.done():
            self._presentation_task = self.hass.async_create_task(
                self._async_presentations()
            )
        self.async_write_ha_state()

    async def _async_presentations(self):
        try:
            while self._presentation_queue and not self._ha_stopping:
                request = self._presentation_queue.popleft()
                try:
                    await self._async_present_native(request)
                except asyncio.CancelledError:
                    raise
                except Exception as err:
                    self._presentation_error = str(err)
                    _LOGGER.warning("Presentation failed: %s", err)
                    self.async_write_ha_state()
        finally:
            self._presentation_active = False
            self._presentation_task = None
            await self.async_refresh()

    async def _async_cancel_presentations(self):
        self._presentation_queue.clear()
        task = self._presentation_task
        if task is not None and task is not asyncio.current_task() and not task.done():
            if not task.cancelling():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self._presentation_task = None

    async def async_clear_content(self):
        await self._async_cancel_presentations()
