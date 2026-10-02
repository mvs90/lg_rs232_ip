"""One display-owned controller; no knowledge of players, soundbars or sockets."""

from __future__ import annotations

import asyncio
from homeassistant.components.media_player import MediaPlayerState
from homeassistant.exceptions import HomeAssistantError
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta

from .const import DOMAIN, INPUT_SOURCES
from .controls import NativeControls


class DisplayController(NativeControls):
    def __init__(self, hass, entry, display):
        self.hass = hass
        self._config_entry = entry
        self._lg_display = display
        self.entity_id = None
        self._ha_stopping = False
        self._state = MediaPlayerState.OFF
        self._last_display_power = None
        self._current_input_id = None
        self._source = None
        self.power = None
        self.volume = None
        self.muted = None
        self.signal = None
        self._listeners = set()
        self._init_controls()
        self._poll_unsub = None
        self._stop_unsub = None
        self._refresh_lock = asyncio.Lock()
        self.external_owner = None

    @property
    def presentation_active(self):
        return (
            self._presentation_active
            or bool(self._presentation_queue)
            or (
                self._presentation_task is not None
                and not self._presentation_task.done()
            )
        )

    def subscribe(self, listener):
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    def async_write_ha_state(self):
        data = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {})
        if alerts := data.get("alert_state"):
            issues = {
                "display_unresponsive": (
                    self.power is None
                    and not self._lg_display.is_intentionally_unpowered,
                    "Display state cannot be confirmed",
                ),
                "presentation_failed": (
                    bool(self._presentation_error),
                    "Native presentation failed; inspect the display entity",
                ),
                "osd_restore_failed": (
                    bool(self._lg_display.osd_restore_error),
                    "OSD restoration is pending",
                ),
            }
            for code, (active, message) in issues.items():
                if active:
                    alerts.set_issue(code, message)
                else:
                    alerts.clear_issue(code)
        self.hass.bus.async_fire(
            "lg_rs232_ip_status", {"entry_id": self._config_entry.entry_id}
        )
        for listener in tuple(self._listeners):
            listener()

    def _resolve_source_name(self, input_id):
        for index in range(1, 4):
            if INPUT_SOURCES[f"HDMI {index}"] == input_id:
                return self._config_entry.options.get(
                    f"input_name_hdmi{index}", f"HDMI {index}"
                )
        return {0xE0: "LG Player", 0xE3: "Website"}.get(input_id)

    async def async_start(self):
        async def stopping(_):
            self._stop_unsub = None  # The one-shot listener has already removed itself.
            await self.async_close()
            app = (
                self.hass.data.get(DOMAIN, {})
                .get(self._config_entry.entry_id, {})
                .get("display_app")
            )
            if app:
                await app.async_close()

        self._stop_unsub = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, stopping
        )

        async def tick(_):
            await self.async_refresh()

        self._poll_unsub = async_track_time_interval(
            self.hass,
            tick,
            timedelta(seconds=self._config_entry.options.get("polling_interval", 30)),
        )
        await self.async_refresh()

    async def async_refresh(self):
        if self._ha_stopping or self._refresh_lock.locked():
            return
        async with self._refresh_lock:
            self.power = await self._lg_display.async_get_power_status(use_cache=False)
            app = (
                self.hass.data.get(DOMAIN, {})
                .get(self._config_entry.entry_id, {})
                .get("display_app")
            )
            if app:
                await app.async_maybe_recover()
            if self.power is True:
                self._current_input_id = await self._lg_display.async_get_input()
                if app and app.logical_input is not None:
                    self._current_input_id = app.logical_input
                self._source = self._resolve_source_name(self._current_input_id)
                self.volume = await self._lg_display.async_get_volume()
                raw = await self._lg_display.async_send_command("k", "e", 0xFF)
                self.muted = raw == 0 if raw is not None else None
                self.signal = await self._lg_display.async_get_signal_status()
            else:
                self.signal = None
            self.async_write_ha_state()

    async def async_ensure_on(self, reason="display action"):
        if await self._lg_display.async_get_power_status(use_cache=False) is True:
            return
        if self._lg_display.is_intentionally_unpowered:
            raise HomeAssistantError(
                "Display has no external power; use the AV system to restore its supply"
            )
        if not await self._lg_display.async_power_on():
            raise HomeAssistantError("LG rejected power on")
        async with asyncio.timeout(
            self._config_entry.options.get("display_wake_timeout", 60)
        ):
            while (
                await self._lg_display.async_get_power_status(use_cache=False)
                is not True
            ):
                await asyncio.sleep(1)
        self.power = True

    async def async_turn_on(self):
        await self.async_clear_content()
        async with self._control_lock:
            await self.async_ensure_on()
        await self.async_refresh()

    async def async_turn_off(self):
        await self.async_clear_content()
        async with self._control_lock:
            if not await self._lg_display.async_power_off():
                raise HomeAssistantError("LG rejected power off")
        await self.async_refresh()

    async def async_select_input(self, input_id):
        await self.async_clear_content()
        async with self._control_lock:
            app = (
                self.hass.data.get(DOMAIN, {})
                .get(self._config_entry.entry_id, {})
                .get("display_app")
            )
            if app:
                await app.async_pause_resident(leave=False)
            if not await self._lg_display.async_set_input(input_id):
                raise HomeAssistantError("LG rejected input")
        await self.async_refresh()

    async def async_close(self):
        self._ha_stopping = True
        if self._poll_unsub:
            self._poll_unsub()
            self._poll_unsub = None
        if self._stop_unsub:
            self._stop_unsub()
            self._stop_unsub = None
        await self._async_cancel_presentations()
        self._listeners.clear()
