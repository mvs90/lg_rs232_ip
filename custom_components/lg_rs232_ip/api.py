"""Public AV adapter API v1. Only this module is a cross-integration contract."""

from contextlib import asynccontextmanager
from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN

API_VERSION = 1


class DisplayAPI:
    def __init__(self, hass, entry_id):
        self.hass = hass
        self.entry_id = entry_id

    @property
    def ready(self):
        data = self.hass.data.get(DOMAIN, {}).get(self.entry_id, {})
        return (
            data.get("controller") is not None and not data["controller"]._ha_stopping
        )

    @property
    def controller(self):
        if not self.ready:
            raise HomeAssistantError("Selected LG integration is not loaded")
        return self.hass.data[DOMAIN][self.entry_id]["controller"]

    @property
    def display(self):
        return self.controller._lg_display

    @property
    def presentation_active(self):
        return self.ready and self.controller.presentation_active

    @property
    def is_available(self):
        return self.ready and self.display.is_available

    @property
    def is_intentionally_unpowered(self):
        return self.ready and self.display.is_intentionally_unpowered

    @property
    def model_name(self):
        return self.display.model_name if self.ready else None

    @property
    def software_version(self):
        return self.display.software_version if self.ready else None

    @property
    def osd_restore_error(self):
        return self.ready and self.display.osd_restore_error

    def set_power_supply_state(self, state):
        if self.ready:
            self.display.set_power_supply_state(state)
            self.controller.async_write_ha_state()

    async def async_get_power_status(self, *, use_cache=True):
        return (
            await self.display.async_get_power_status(use_cache=use_cache)
            if self.ready
            else None
        )

    async def async_get_input(self, *, use_cache=True):
        return (
            await self.display.async_get_input(use_cache=use_cache)
            if self.ready
            else None
        )

    async def async_get_signal_status(self):
        return await self.display.async_get_signal_status() if self.ready else None

    async def async_get_volume(self):
        return await self.display.async_get_volume() if self.ready else None

    async def async_get_mute_raw(self):
        return (
            await self.display.async_send_command("k", "e", 0xFF)
            if self.ready
            else None
        )

    async def _write(self, method, *args):
        controller = self.controller
        async with controller._control_lock:
            if controller.presentation_active:
                raise HomeAssistantError("LG native presentation is active")
            return await getattr(self.display, method)(*args)

    async def async_power_on(self):
        return await self._write("async_power_on")

    async def async_power_off(self):
        return await self._write("async_power_off")

    async def async_set_input(self, value):
        return await self._write("async_set_input", value)

    async def async_set_volume(self, value):
        return await self._write("async_set_volume", value)

    async def async_set_mute_raw(self, value):
        return await self._write("async_send_command", "k", "e", value)

    async def async_volume_up_step(self):
        return await self._write("async_volume_up_step")

    async def async_volume_down_step(self):
        return await self._write("async_volume_down_step")

    async def async_send_remote_key(self, key):
        return await self._write("async_send_remote_key", key)

    async def async_begin_external_presentation(self):
        import secrets

        controller = self.controller
        async with controller._control_lock:
            if controller.presentation_active or controller.external_owner is not None:
                raise HomeAssistantError("Display is busy with another presentation")
            token = secrets.token_hex(16)
            controller.external_owner = token
            return token

    async def async_end_external_presentation(self, token):
        if self.ready and self.controller.external_owner == token:
            self.controller.external_owner = None

    async def async_clear_content(self):
        await self.controller.async_clear_content()

    async def async_present(self, action, **kwargs):
        if action not in {
            "show_toast",
            "show_display_app",
            "show_native_image",
            "show_native_video",
            "show_website",
            "show_stream",
            "prepare_boot_image",
        }:
            raise HomeAssistantError("Unsupported LG presentation action")
        return await getattr(self.controller, "async_" + action)(**kwargs)

    @asynccontextmanager
    async def supply_guard(self):
        """Hold LG commands while the caller cuts an already-confirmed-off supply."""
        controller = self.controller
        async with controller._control_lock:
            allowed = (
                not controller.presentation_active
                and controller.external_owner is None
                and await self.display.async_get_power_status(use_cache=False) is False
            )
            yield allowed


def get_display_api(hass, entry_id, *, version=1):
    if version != API_VERSION:
        raise HomeAssistantError("Unsupported LG Display API version")
    return DisplayAPI(hass, entry_id)
