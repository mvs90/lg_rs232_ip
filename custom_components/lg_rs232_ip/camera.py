"""Throttled native screenshot camera; no invented RTSP/video-stream support."""

from __future__ import annotations

import asyncio
import time

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .web_manager import LGWebError


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    if entry.options.get("preview_enabled", False) and data.get("web_manager"):
        async_add_entities(
            [LGDisplayPreview(entry, data["lg_display"], data["web_manager"])]
        )


class LGDisplayPreview(Camera):
    """Keep one in-memory frame. Concurrent viewers never multiply captures."""

    _attr_has_entity_name = True
    _attr_name = "Display preview"
    _attr_supported_features = CameraEntityFeature.ON_OFF
    _attr_should_poll = False
    _attr_is_streaming = False

    def __init__(self, entry, display, web):
        super().__init__()
        self._attr_unique_id = f"{entry.entry_id}_preview"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})
        self._display = display
        self._web = web
        self._interval = entry.options.get("preview_interval", 30)
        self._height = int(entry.options.get("preview_height", "720"))
        self._image = None
        self._captured_at = None
        self._error = None
        self._next_capture = 0.0
        self._lock = asyncio.Lock()
        self._removed = False
        self._refresh_task = None
        self._timer_unsub = None
        self._attr_available = True
        self.content_type = "image/jpeg"

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        await self.async_update()

    async def _async_tick(self, _now):
        await self.async_update()

    async def async_update(self):
        # Also used by camera_image: HA clients cannot bypass the configured rate.
        async with self._lock:
            if self._removed or not self._attr_is_on:
                return
            if time.monotonic() < self._next_capture:
                return
            self._next_capture = time.monotonic() + self._interval
            self._refresh_task = asyncio.current_task()
            try:
                power = await self._display.async_get_power_status(use_cache=False)
                if self._removed or not self._attr_is_on:
                    return
                if power is not True:
                    self._image = None
                    self._captured_at = None
                    self._error = "display_off" if power is False else "power_unknown"
                    self._attr_available = power is False
                    return
                image = await self._web.async_capture(self._height)
                if not self._removed and self._attr_is_on:
                    self._image = image
                    self._captured_at = dt_util.utcnow()
                    self._error = None
                    self._attr_available = True
            except LGWebError:
                # Never show an old image as if it were current after a failed capture.
                self._image = None
                self._captured_at = None
                if self._attr_is_on:
                    self._error = "capture_failed"
                    self._attr_available = False
            finally:
                self._next_capture = time.monotonic() + self._interval
                self._refresh_task = None
                if not self._removed:
                    if self._timer_unsub:
                        self._timer_unsub()
                    if self._attr_is_on:
                        self._timer_unsub = async_call_later(
                            self.hass, self._interval, self._async_tick
                        )
                    self.async_write_ha_state()

    async def async_camera_image(self, width=None, height=None):
        await self.async_update()
        return self._image if self._attr_is_on else None

    @property
    def extra_state_attributes(self):
        return {
            "preview_mode": "periodic_screenshot",
            "refresh_interval": self._interval,
            "capture_height": self._height,
            "last_capture": self._captured_at,
            "preview_error": self._error,
        }

    async def async_turn_off(self):
        # Stop preview collection only; never change panel power.
        self._attr_is_on = False
        self._attr_available = True
        self._error = None
        if self._timer_unsub:
            self._timer_unsub()
            self._timer_unsub = None
        self._image = None
        self._captured_at = None
        self.async_write_ha_state()

    async def async_turn_on(self):
        self._attr_is_on = True
        self._next_capture = 0
        await self.async_update()

    async def async_will_remove_from_hass(self):
        self._removed = True
        if self._timer_unsub:
            self._timer_unsub()
            self._timer_unsub = None
        if self._refresh_task and self._refresh_task is not asyncio.current_task():
            self._refresh_task.cancel()
            await asyncio.gather(self._refresh_task, return_exceptions=True)
        self._image = None
        await super().async_will_remove_from_hass()
