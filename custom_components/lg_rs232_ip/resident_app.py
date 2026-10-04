"""Optional SI lifecycle; an idle HDMI app never owns a presentation lease."""

import asyncio
import secrets
import time

from homeassistant.exceptions import HomeAssistantError

from .web_manager import LGWebError

SI_APP_ID = "commercial.signage.signageapplauncher"
EXTERNAL_APPS = {f"com.webos.app.hdmi{i}" for i in range(1, 5)}


class ResidentApp:
    def _init_resident(self):
        self.resident = (
            self.enabled
            and self.mode == "si"
            and self.entry.options.get("display_app_resident", False)
        )
        self._resident_power = None
        self._resident_foreground = None
        self._resident_retry = 0.0
        self._resident_started = 0.0
        self._input_request = None
        self._input_applied = asyncio.Event()

    @property
    def resident_connected(self):
        return bool(
            self.resident
            and self.connected
            and self.saved.get("resident")
            and not self.saved.get("paused")
            and self._resident_foreground == SI_APP_ID
        )

    @property
    def dashboard_available(self):
        return bool(self.resident and self.layouts and self.layouts.config["enabled"])

    @property
    def dashboard_selected(self):
        return bool(
            self.dashboard_available
            and self.saved.get("dashboard")
            and not self.saved.get("paused")
        )

    async def async_select_dashboard(self):
        await self.async_select_view("dashboard")

    @property
    def pip_selected(self):
        return bool(
            self.dashboard_available
            and self.saved.get("pip")
            and not self.saved.get("paused")
        )

    async def async_select_pip(self):
        await self.async_select_view("pip")

    async def async_select_view(self, view):
        if view not in ("dashboard", "pip"):
            raise HomeAssistantError("Unknown app view")
        if not self.dashboard_available or not self.resident_connected:
            raise HomeAssistantError(
                "Enable custom layouts and connect the resident display app first"
            )
        if (view == "dashboard" and self.dashboard_selected) or (
            view == "pip" and self.pip_selected
        ):
            return
        from .native_presentations import settle_mutation

        _, cancelled = await settle_mutation(
            self._async_apply_hdmi(
                self.selected_input,
                self.selected_app,
                dashboard=view == "dashboard",
                pip=view == "pip",
            )
        )
        if cancelled:
            raise asyncio.CancelledError

    @property
    def logical_input(self):
        return self.selected_input if self.resident_connected else None

    @property
    def selected_input(self):
        return self.saved.get("selected_input", self.saved.get("original_input"))

    @property
    def selected_app(self):
        selected = self.saved.get("selected_app")
        if selected in EXTERNAL_APPS:
            return selected
        value = self.selected_input
        if value in (0x90, 0x91, 0x92):
            return f"com.webos.app.hdmi{value - 0x90 + 1}"
        return self.saved.get("original_app")

    def idle_hdmi(self):
        original = self.selected_app
        if (
            self.resident
            and self.saved.get("resident")
            and not self.saved.get("paused")
            and original in EXTERNAL_APPS
        ):
            return "ext://hdmi:" + original[-1]
        return None

    async def async_select_hdmi(self, input_id):
        """Called under the control lock. A missing signal is not an app failure."""
        if not self.resident_connected or input_id not in (0x90, 0x91, 0x92):
            return False
        target_app = f"com.webos.app.hdmi{input_id - 0x90 + 1}"
        if (
            self.selected_input == input_id
            and self.selected_app == target_app
            and not self.saved.get("dashboard")
            and not self.saved.get("pip")
        ):
            return True
        from .native_presentations import settle_mutation

        # Finish the bounded source/OSD transaction even if the service caller
        # disconnects. Never leave a new input paired with an old recovery journal.
        _, cancelled = await settle_mutation(
            self._async_apply_hdmi(input_id, target_app)
        )
        if cancelled:
            raise asyncio.CancelledError
        return True

    async def _async_apply_hdmi(
        self, input_id, target_app, *, dashboard=False, pip=False
    ):
        previous_dashboard = self.saved.get("dashboard", False)
        previous_pip = self.saved.get("pip", False)
        previous = self.selected_input
        previous_app = self.selected_app
        self._input_request = secrets.token_hex(16)
        self._input_applied.clear()
        try:
            async with self.controller._lg_display.async_suppress_osd_for_switch():
                self.saved["dashboard"] = dashboard
                self.saved["pip"] = pip
                self.saved["selected_input"] = input_id
                self.saved["selected_app"] = target_app
                if self.content:
                    self.content["hdmi"] = self.idle_hdmi()
                self.changed()
                try:
                    await asyncio.wait_for(self._input_applied.wait(), 5)
                except TimeoutError:
                    # Publish rollback before the guard restores OSD.
                    self.saved["dashboard"] = previous_dashboard
                    self.saved["pip"] = previous_pip
                    self.saved["selected_input"] = previous
                    self.saved["selected_app"] = previous_app
                    self._input_request = None
                    if self.content:
                        self.content["hdmi"] = self.idle_hdmi()
                    self.changed()
                    raise HomeAssistantError(
                        "Display app did not confirm HDMI selection"
                    ) from None
                await self.store.async_save(self.saved)
        finally:
            self._input_request = None
            self._notify()

    async def async_resume(self):
        if not self.resident:
            raise HomeAssistantError("Enable resident SI mode in LG options first")
        self.saved.pop("paused", None)
        self.saved.pop("auto_retry", None)
        self._resident_foreground = None
        self._resident_retry = 0
        await self.store.async_save(self.saved)
        await self.async_maintain_resident()

    async def async_pause_resident(self, *, leave=True):
        """Respect explicit input changes until resume or a confirmed wake cycle."""
        if not self.saved.get("resident"):
            return
        self.saved["paused"] = True
        self.saved.pop("auto_retry", None)
        self._resident_foreground = None
        self.last_seen = 0
        self.changed()
        await self.store.async_save(self.saved)
        if (
            leave
            and await self.web.async_foreground_app() == SI_APP_ID
            and await self.async_owns_si()
        ):
            async with self.controller._lg_display.async_suppress_osd_for_switch():
                await self.web.async_launch_app(self.selected_app)

    async def async_maintain_resident(self, *, power="query"):
        controller = self.controller
        if power == "query":
            power = await controller._lg_display.async_get_power_status(use_cache=False)
        previous_power, self._resident_power = self._resident_power, power
        if power is not True:
            self._resident_foreground = None
            self._resident_started = 0
            self.last_seen = 0
            return
        if not self.resident or self.closed or controller._ha_stopping:
            return
        if (
            controller._control_lock.locked()
            or controller.presentation_active
            or controller.external_owner
        ):
            return
        if previous_power is False or (
            self.saved.get("auto_retry") and time.monotonic() >= self._resident_retry
        ):
            self.saved.pop("paused", None)
            self.saved.pop("auto_retry", None)
            self._resident_retry = 0
            await self.store.async_save(self.saved)
        if self.saved.get("paused") or (
            time.monotonic() < self._resident_retry and not self.connected
        ):
            return
        async with controller._control_lock:
            try:
                foreground = await self.web.async_foreground_app()
                if self.saved.get("resident"):
                    if not await self.async_owns_si():
                        self._resident_foreground = None
                        raise HomeAssistantError(
                            "SI settings changed outside Home Assistant"
                        )
                    if foreground == SI_APP_ID:
                        self._resident_foreground = foreground
                        if self.resident_connected:
                            self.last_error = None
                            self._resident_retry = 0
                        if not self._resident_started:
                            self._resident_started = time.monotonic()
                        if (
                            not self.resident_connected
                            and time.monotonic() - self._resident_started > 30
                        ):
                            # The loaded app keeps HDMI alive during a network outage.
                            # Leaving/relaunching it would create repeated blackouts.
                            self.last_error = "resident_connection_lost"
                        return
                    if self._resident_foreground == SI_APP_ID:
                        # A physical source change wins over the optional resident app.
                        await self.async_pause_resident(leave=False)
                        return
                if foreground not in EXTERNAL_APPS:
                    return
                # Explicit SI restoration can leave the feature enabled but paused.
                if not self.saved.get("resident"):
                    await self.async_prepare_si(foreground, True, resident=True)
                elif foreground != self.selected_app:
                    # Explicit Resume (or a wake cycle) adopts the current HDMI.
                    self.saved["selected_app"] = foreground
                    self.saved[
                        "selected_input"
                    ] = await controller._lg_display.async_get_input(use_cache=False)
                    await self.store.async_save(self.saved)
                self.last_seen = 0
                self.client_hdmi = False
                self._resident_started = time.monotonic()
                async with controller._lg_display.async_suppress_osd_for_switch():
                    await self.web.async_launch_app(SI_APP_ID)
                self._resident_foreground = SI_APP_ID
                self.last_error = None
            except (LGWebError, HomeAssistantError):
                self.last_error = "resident_start_failed"
                self._resident_retry = time.monotonic() + 30
            finally:
                self._notify()

    async def async_present_connected(self, request):
        """Use the existing foreground app; never launch an app in this path."""
        if not self.resident_connected:
            return False
        controller = self.controller
        identifier = None
        async with controller._control_lock:
            controller._check_presentation_policy(request["priority"])
            # Foreground/settings are verified by maintenance; the short-lived,
            # versioned visibility heartbeat is the fast-path liveness check.
            if not self.resident_connected or controller.external_owner:
                return False
            identifier = self.begin(
                request["title"],
                request["message"],
                request["duration"],
                request["dashboard"],
                request.get("layout", "fullscreen"),
            )
            controller._resident_request = request
            controller._resident_replace.clear()
            controller._presentation_error = None
            self.content["hdmi"] = self.idle_hdmi()
            controller._presentation_active = True
            controller.async_write_ha_state()
        rendered = asyncio.create_task(self.wait_rendered(identifier))
        replaced = asyncio.create_task(controller._resident_replace.wait())
        try:
            done, _ = await asyncio.wait(
                (rendered, replaced), return_when=asyncio.FIRST_COMPLETED
            )
            if replaced in done:
                return True
            await rendered
            end = time.monotonic() + request["duration"]
            while time.monotonic() < end:
                if not self.connected:
                    raise HomeAssistantError(
                        "Display app disconnected during presentation"
                    )
                try:
                    await asyncio.wait_for(
                        controller._resident_replace.wait(),
                        min(1, end - time.monotonic()),
                    )
                    return True
                except TimeoutError:
                    pass
            return True
        finally:
            for task in (rendered, replaced):
                task.cancel()
            await asyncio.gather(rendered, replaced, return_exceptions=True)
            self.end(identifier)
            controller._resident_request = None
            controller._presentation_active = False
            controller.async_write_ha_state()
