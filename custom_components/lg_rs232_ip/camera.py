"""Shared LG screenshots with a browser-compatible, demand-driven MJPEG view."""

from __future__ import annotations

import asyncio
import base64
import time

from aiohttp import web as aiohttp_web
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .web_manager import LGWebError

# A neutral JPEG clears a stream's last frame when the display/capture is unavailable.
# Generated locally; it contains no display data.
_EMPTY_FRAME = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAAJABADASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFAEBAAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AI+AD//Z"
)
_BOUNDARY = "lg-display-frame"


def _mjpeg_part(image: bytes) -> bytes:
    return (
        (
            f"--{_BOUNDARY}\r\nContent-Type: image/jpeg\r\n"
            f"Content-Length: {len(image)}\r\n\r\n"
        ).encode()
        + image
        + b"\r\n"
    )


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    if entry.options.get("preview_enabled", False) and data.get("web_manager"):
        async_add_entities(
            [LGDisplayPreview(entry, data["lg_display"], data["web_manager"])]
        )


class LGDisplayPreview(Camera):
    """All viewers share one capture; faster only while a stream is open."""

    _attr_has_entity_name = True
    _attr_name = "Display preview"
    _attr_supported_features = CameraEntityFeature.ON_OFF
    _attr_should_poll = False
    _attr_is_streaming = False
    # Fast frame timestamps are UI telemetry, not history: avoid one recorder row per second.
    _unrecorded_attributes = frozenset({"last_capture"})

    def __init__(self, entry, display, web):
        super().__init__()
        self._attr_unique_id = f"{entry.entry_id}_preview"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})
        self._display = display
        self._web = web
        self._interval = entry.options.get("preview_interval", 30)
        self._active_interval = entry.options.get("preview_active_interval", 1)
        self._height = int(entry.options.get("preview_height", "720"))
        self._image = None
        self._captured_at = None
        self._error = None
        self._next_capture = 0.0
        self._last_started = 0.0
        self._last_finished = 0.0
        self._retry_at = 0.0
        self._failures = 0
        self._generation = 0
        self._active_viewers = 0
        self._removed = False
        self._refresh_task = None
        self._timer_unsub = None
        self._attr_available = True
        self.content_type = "image/jpeg"

    @property
    def _effective_interval(self):
        if self._active_viewers and self._active_interval:
            return min(self._interval, self._active_interval)
        return self._interval

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        await self.async_update()

    def _cancel_timer(self):
        if self._timer_unsub:
            self._timer_unsub()
            self._timer_unsub = None

    def _schedule(self):
        self._cancel_timer()
        if not self._removed and self._attr_is_on and not self._refresh_task:
            self._timer_unsub = async_call_later(
                self.hass,
                max(0.05, self._next_capture - time.monotonic()),
                self._async_tick,
            )

    def _viewers_changed(self, delta):
        self._active_viewers = max(0, self._active_viewers + delta)
        self._attr_is_streaming = bool(self._active_viewers)
        self._next_capture = max(
            self._last_started + self._effective_interval,
            self._last_finished + 0.1,
            self._retry_at,
        )
        self._schedule()
        if not self._removed:
            self.async_write_ha_state()

    async def _async_tick(self, _now):
        self._timer_unsub = None
        await self.async_update()

    async def async_update(self):
        if self._removed or not self._attr_is_on:
            return
        if self._refresh_task is None:
            if time.monotonic() < self._next_capture:
                self._schedule()
                return
            self._cancel_timer()
            self._refresh_task = asyncio.create_task(self._async_capture())
        # Closing a browser/request must not cancel a capture shared by other viewers.
        await asyncio.shield(self._refresh_task)

    async def _async_capture(self):
        generation = self._generation
        self._last_started = time.monotonic()
        try:
            power = await self._display.async_get_power_status(use_cache=False)
            if self._removed or not self._attr_is_on or generation != self._generation:
                return
            if power is not True:
                self._image = None
                self._captured_at = None
                self._error = "display_off" if power is False else "power_unknown"
                self._attr_available = power is False
                return
            image = await self._web.async_capture(self._height)
            if (
                not self._removed
                and self._attr_is_on
                and generation == self._generation
            ):
                self._image = image
                self._captured_at = dt_util.utcnow()
                self._error = None
                self._failures = 0
                self._retry_at = 0.0
                self._attr_available = True
        except LGWebError:
            if generation == self._generation and self._attr_is_on:
                self._image = None
                self._captured_at = None
                self._error = "capture_failed"
                self._attr_available = False
                self._failures += 1
                self._retry_at = time.monotonic() + min(30, 2 ** min(self._failures, 5))
        finally:
            self._last_finished = time.monotonic()
            self._next_capture = (
                max(
                    self._last_started + self._effective_interval,
                    self._last_finished + 0.1,
                    self._retry_at,
                )
                if generation == self._generation
                else 0.0
            )
            self._refresh_task = None
            self._schedule()
            if not self._removed:
                self.async_write_ha_state()

    async def async_camera_image(self, width=None, height=None):
        await self.async_update()
        return self._image if self._attr_is_on else None

    async def handle_async_mjpeg_stream(self, request):
        return await self.handle_async_still_stream(request, 0.5)

    async def handle_async_still_stream(self, request, interval):
        """Correct multipart framing, including recovery from an empty first capture."""
        # WebKit rejects multipart MIME responses in fetch(). The bundled card
        # requests identical length-delimited parts as binary data so AbortController
        # can close the connection reliably; native HA image views still use MJPEG.
        content_type = (
            "application/octet-stream"
            if request.query.get("lg_preview") == "frames"
            else f"multipart/x-mixed-replace; boundary={_BOUNDARY}"
        )
        response = aiohttp_web.StreamResponse(
            headers={
                "Content-Type": content_type,
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "X-Accel-Buffering": "no",
            }
        )
        self._viewers_changed(1)
        first = True
        try:
            await response.prepare(request)
            while not self._removed and self._attr_is_on:
                started = time.monotonic()
                if request.transport is None or request.transport.is_closing():
                    break
                image = await self.async_camera_image()
                # Keep the stream alive through temporary failures and actively erase stale pixels.
                part = _mjpeg_part(image or _EMPTY_FRAME)
                async with asyncio.timeout(5):
                    await response.write(part)
                    if first:
                        # Chromium initially displays the preceding multipart frame.
                        await response.write(part)
                        first = False
                await asyncio.sleep(
                    max(0.05, started + max(0.5, min(interval, 1)) - time.monotonic())
                )
            if request.transport and not request.transport.is_closing():
                async with asyncio.timeout(5):
                    await response.write(
                        _mjpeg_part(_EMPTY_FRAME) + f"--{_BOUNDARY}--\r\n".encode()
                    )
        except (ConnectionError, TimeoutError):
            pass
        finally:
            self._viewers_changed(-1)
        return response

    @property
    def extra_state_attributes(self):
        return {
            "preview_mode": "periodic_screenshot",
            "collection_enabled": self._attr_is_on,
            "refresh_interval": self._interval,
            "active_refresh_interval": self._active_interval,
            "effective_refresh_interval": self._effective_interval,
            "active_viewers": self._active_viewers,
            "capture_height": self._height,
            "last_capture": self._captured_at,
            "preview_error": self._error,
        }

    async def async_turn_off(self):
        self._attr_is_on = False
        self._generation += 1
        self._attr_available = True
        self._error = None
        self._cancel_timer()
        self._image = None
        self._captured_at = None
        self.async_write_ha_state()

    async def async_turn_on(self):
        self._attr_is_on = True
        self._next_capture = 0
        self._retry_at = 0
        self._failures = 0
        await self.async_update()

    async def async_will_remove_from_hass(self):
        self._removed = True
        self._generation += 1
        self._cancel_timer()
        if self._refresh_task:
            self._refresh_task.cancel()
            await asyncio.gather(self._refresh_task, return_exceptions=True)
        self._image = None
        await super().async_will_remove_from_hass()
