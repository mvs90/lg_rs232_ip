"""Optional SI lifecycle; an idle HDMI app never owns a presentation lease."""

import asyncio
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

    @property
    def resident_connected(self):
        return bool(
            self.resident
            and self.connected
            and self.client_hdmi
            and self.saved.get("resident")
            and not self.saved.get("paused")
            and self._resident_foreground == SI_APP_ID
        )

    @property
    def logical_input(self):
        return self.saved.get("original_input") if self.resident_connected else None

    def idle_hdmi(self):
        original = self.saved.get("original_app")
        if (
            self.resident
            and self.saved.get("resident")
            and not self.saved.get("paused")
            and original in EXTERNAL_APPS
        ):
            return "ext://hdmi:" + original[-1]
        return None

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
                await self.web.async_launch_app(self.saved["original_app"])

    async def async_maintain_resident(self):
        controller = self.controller
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
                            await self.async_pause_resident()
                            self.last_error = "resident_connection_lost"
                            self.saved["auto_retry"] = True
                            self._resident_retry = time.monotonic() + 60
                            self._resident_started = 0
                            await self.store.async_save(self.saved)
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
                elif foreground != self.saved.get("original_app"):
                    await self.async_pause_resident(leave=False)
                    return
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
                self.changed()
                self._notify()

    async def async_present_connected(self, request):
        """Use the existing foreground app; never launch an app in this path."""
        if not self.connected or self.mode != "si":
            return False
        controller = self.controller
        identifier = None
        async with controller._control_lock:
            controller._check_presentation_policy(request["priority"])
            if (
                await controller._lg_display.async_get_power_status(use_cache=False)
                is not True
                or await self.web.async_foreground_app() != SI_APP_ID
                or not await self.async_owns_si()
            ):
                return False
            identifier = self.begin(
                request["title"],
                request["message"],
                request["duration"],
                request["dashboard"],
                request.get("layout", "fullscreen"),
            )
            self.content["hdmi"] = self.idle_hdmi()
            controller._presentation_active = True
            controller.async_write_ha_state()
        try:
            await self.wait_rendered(identifier)
            end = time.monotonic() + request["duration"]
            while time.monotonic() < end:
                if not self.connected:
                    raise HomeAssistantError(
                        "Display app disconnected during presentation"
                    )
                await asyncio.sleep(min(1, end - time.monotonic()))
            return True
        finally:
            self.end(identifier)
            controller._presentation_active = False
            controller.async_write_ha_state()
