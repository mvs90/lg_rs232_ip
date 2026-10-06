"""One display-owned controller; no knowledge of players, soundbars or sockets."""

from __future__ import annotations

import asyncio
from contextlib import nullcontext
from time import monotonic
from homeassistant.components.media_player import MediaPlayerState
from homeassistant.exceptions import HomeAssistantError
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta

from .const import DOMAIN, INPUT_SOURCES
from .controls import NativeControls
from .temporary_view import TemporaryView


class DisplayController(TemporaryView, NativeControls):
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
        self._init_temporary_view()
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
            data = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {})
            if app := data.get("display_app"):
                await app.async_close()
            if layouts := data.get("layouts"):
                await layouts.async_close()

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
                await app.async_maybe_recover(power=self.power)
            if self.power is True:
                self._current_input_id = await self._lg_display.async_get_input()
                if app and app.logical_input is not None:
                    self._current_input_id = app.logical_input
                self._source = (
                    self.app_view_sources.get(app.selected_view)
                    if app and app.selected_view and app.resident_connected
                    else self._resolve_source_name(self._current_input_id)
                )
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

    @property
    def app_view_sources(self):
        from .layout_library import SOURCE_VIEWS, source_names

        app = (
            self.hass.data.get(DOMAIN, {})
            .get(self._config_entry.entry_id, {})
            .get("display_app")
        )
        views = app.view_sources if app else SOURCE_VIEWS
        occupied = [
            self._config_entry.options.get(f"input_name_hdmi{i}", f"HDMI {i}")
            for i in range(1, 4)
        ]
        return source_names(views, occupied)

    async def async_select_dashboard(self):
        await self.async_select_app_view("dashboard")

    async def async_select_pip(self):
        await self.async_select_app_view("pip")

    async def async_select_media_view(self):
        await self.async_select_app_view("media_view")

    async def _async_wait_for_resident(self, app, generation, action):
        """Wait through LG web-service startup, actively retrying bounded maintenance.

        Power-on ACK precedes web/SI readiness. Do not depend on the normal
        polling phase, restart a loading SI app or discard the requested view
        after the former 30-second heartbeat-only wait.
        """

        def current():
            return generation == self._view_generation and not self._ha_stopping

        if not current():
            return False
        if app.resident_connected:
            return True
        timeout = max(90, self._config_entry.options.get("display_wake_timeout", 60))
        deadline = monotonic() + timeout
        try:
            async with asyncio.timeout(timeout):
                await app.async_resume()
                next_retry = monotonic() + 5
                while current():
                    if self.external_owner or self.presentation_active:
                        raise HomeAssistantError(
                            "Display is busy with another presentation"
                        )
                    if app.resident_connected:
                        return True
                    now = monotonic()
                    if now >= deadline:
                        raise TimeoutError
                    if now >= next_retry:
                        # The manager honours its web-error backoff and preserves
                        # an already running SI app while its heartbeat catches up.
                        await app.async_maintain_resident()
                        next_retry = monotonic() + 5
                        continue
                    await asyncio.sleep(min(0.25, deadline - now))
        except TimeoutError:
            if not current():
                return False
            self._view_pending_previous = None
            raise HomeAssistantError(
                f"Display app did not connect for {action} within {timeout} seconds"
            ) from None
        return False

    async def async_select_app_view(self, view, *, transition="none", duration=0, theme=None):
        view = "pip_view" if view == "pip" else view
        if type(duration) is not int or not 0 <= duration <= 3600:
            raise HomeAssistantError("Use a view duration between 0 and 3600 seconds")
        if duration:
            self._check_presentation_policy("normal")
        if transition not in ("none", "smooth"):
            raise HomeAssistantError("Unknown view transition")
        if view != "hdmi_full" and view not in self.app_view_sources:
            raise HomeAssistantError("Unknown app view")
        app = (
            self.hass.data.get(DOMAIN, {})
            .get(self._config_entry.entry_id, {})
            .get("display_app")
        )
        if not app or not app.dashboard_available:
            raise HomeAssistantError(
                "Enable custom layouts and resident SI mode in LG settings first"
            )
        if self.external_owner:
            raise HomeAssistantError("An external presentation owns the display")
        if theme is not None:
            try:
                app.layouts.validate_theme(theme)
            except ValueError as err:
                raise HomeAssistantError(str(err)) from err
        previous = (
            self._view_lease["previous"]
            if duration and self._view_lease
            else self._view_pending_previous
            if duration and self._view_pending_previous
            else (app.selected_view or "hdmi_full", app.selected_input)
        )
        await self.async_clear_content()
        generation = self._view_generation
        with app.starting(view, generation):
            self._view_pending_previous = previous if duration else None
            async with self._control_lock:
                await self.async_ensure_on("app view selection")
            if not await self._async_wait_for_resident(app, generation, "view selection"):
                return
            async with self._control_lock:
                if generation != self._view_generation:
                    return
                if self.external_owner or self.presentation_active:
                    raise HomeAssistantError("Display is busy with another presentation")
                if view == "hdmi_full":
                    input_id = app.selected_input
                    if input_id not in (0x90, 0x91, 0x92):
                        raise HomeAssistantError("Select an HDMI input first")
                    await app.async_select_hdmi(input_id, transition=transition)
                    self._current_input_id = input_id
                    self._source = self._resolve_source_name(input_id)
                else:
                    await app.async_select_view(view, transition=transition)
                    self._source = self.app_view_sources[view]
                if theme is not None:
                    try:
                        await app.layouts.async_set_theme(theme)
                    except ValueError as err:
                        raise HomeAssistantError(str(err)) from err
                self.async_write_ha_state()
                if duration:
                    self._schedule_view_return(
                        app, previous, view, duration, transition, generation
                    )

    async def async_select_input(self, input_id, *, via_app=None):
        """Auto-route media players; explicit select options choose app or native HDMI."""
        if input_id not in INPUT_SOURCES.values():
            raise HomeAssistantError("Unknown LG input")
        app = (
            self.hass.data.get(DOMAIN, {})
            .get(self._config_entry.entry_id, {})
            .get("display_app")
        )
        if via_app is True:
            if not app or not app.resident:
                raise HomeAssistantError("Enable resident SI mode in LG options first")
            if self.external_owner:
                raise HomeAssistantError("An external presentation owns the display")
        await self.async_clear_content()
        startup = (
            app.starting("hdmi_full", self._view_generation)
            if via_app is True
            else nullcontext()
        )
        with startup:
            if via_app is True:
                generation = self._view_generation
                async with self._control_lock:
                    await self.async_ensure_on("app HDMI selection")
                if not await self._async_wait_for_resident(
                    app, generation, "HDMI selection"
                ):
                    return
            async with self._control_lock:
                if via_app is True and generation != self._view_generation:
                    return
                if via_app is True and self.external_owner:
                    raise HomeAssistantError("An external presentation owns the display")
                if app:
                    if via_app is not False and await app.async_select_hdmi(input_id):
                        self._current_input_id = input_id
                        self._source = self._resolve_source_name(input_id)
                        self.async_write_ha_state()
                        return
                    if via_app is True:
                        raise HomeAssistantError(
                            "Display app disconnected during HDMI selection"
                        )
                    app.saved.pop("dashboard", None)
                    app.saved.pop("pip", None)
                    app.saved.pop("media_view", None)
                    app.saved.pop("custom_view", None)
                    await app.async_pause_resident(leave=False)
                if not await self._lg_display.async_set_input(input_id):
                    raise HomeAssistantError("LG rejected input")
            await self.async_refresh()

    async def async_close(self):
        self._ha_stopping = True
        self._cancel_temporary_view()
        if self._poll_unsub:
            self._poll_unsub()
            self._poll_unsub = None
        if self._stop_unsub:
            self._stop_unsub()
            self._stop_unsub = None
        await self._async_cancel_presentations()
        self._listeners.clear()
