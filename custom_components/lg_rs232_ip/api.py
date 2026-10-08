"""Public AV adapter API v1. Only this module is a cross-integration contract."""

from contextlib import asynccontextmanager
from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN

API_VERSION = 1
STUDIO_API_VERSION = 1


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
    def studio_api_version(self):
        return STUDIO_API_VERSION

    @property
    def studio_status(self):
        app = self.hass.data.get(DOMAIN, {}).get(self.entry_id, {}).get("display_app")
        return {
            "app_enabled": bool(app and app.enabled),
            "resident_enabled": bool(app and app.resident),
            "connected": bool(app and app.resident_connected),
            "client_startup_design": dict(app.client_startup_design) if app else {},
            "capabilities": {
                "hdmi": True,
                "pip": True,
                "overlay": True,
                "startup": True,
                "screenshot": True,
            },
        }

    async def async_bind_studio(self, owner, layouts, assets, version):
        data = self.hass.data.get(DOMAIN, {}).get(self.entry_id, {})
        if not self.ready:
            return False
        current = data.get("studio_owner")
        if current not in (None, owner):
            raise HomeAssistantError("Another Display Studio entry owns this display")
        data["studio_owner"], data["layouts"] = owner, layouts
        app = data.get("display_app")
        if app:
            app.bind_studio(owner, layouts, assets, version)
        return True

    async def async_unbind_studio(self, owner):
        data = self.hass.data.get(DOMAIN, {}).get(self.entry_id, {})
        if data.get("studio_owner") != owner:
            return
        if app := data.get("display_app"):
            app.unbind_studio(owner)
        data.pop("layouts", None)
        data.pop("studio_owner", None)

    async def async_show_studio_view(self, view, **kwargs):
        await self.controller.async_select_app_view(view, **kwargs)

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
        return self.ready and (
            self.controller.presentation_active
            or self.dashboard_active
            or self.pip_active
            or self.media_view_active
            or self.active_view is not None
        )

    @property
    def dashboard_available(self):
        app = self.hass.data.get(DOMAIN, {}).get(self.entry_id, {}).get("display_app")
        return bool(self.ready and app and app.dashboard_available)

    @property
    def dashboard_active(self):
        if not self.ready:
            return False
        app = self.hass.data[DOMAIN][self.entry_id].get("display_app")
        return bool(
            app and app.dashboard_selected and self.controller.power is not False
        )

    async def async_select_dashboard(self):
        await self.controller.async_select_dashboard()

    @property
    def pip_available(self):
        return self.dashboard_available

    @property
    def pip_active(self):
        if not self.ready:
            return False
        app = self.hass.data[DOMAIN][self.entry_id].get("display_app")
        return bool(app and app.pip_selected and self.controller.power is not False)

    async def async_select_pip(self):
        await self.controller.async_select_pip()

    @property
    def media_view_available(self):
        return self.dashboard_available

    @property
    def media_view_active(self):
        if not self.ready:
            return False
        app = self.hass.data[DOMAIN][self.entry_id].get("display_app")
        return bool(
            app and app.media_view_selected and self.controller.power is not False
        )

    async def async_select_media_view(self):
        await self.controller.async_select_media_view()

    @property
    def view_sources(self):
        return self.controller.app_view_sources if self.dashboard_available else {}

    @property
    def active_view(self):
        if not self.ready or self.controller.power is False:
            return None
        app = self.hass.data[DOMAIN][self.entry_id].get("display_app")
        selected = getattr(app, "selected_view", None) if app else None
        return selected if isinstance(selected, str) else None

    async def async_select_view(self, view_id):
        await self.controller.async_select_app_view(view_id)

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
        if self.ready:
            app = self.hass.data[DOMAIN][self.entry_id].get("display_app")
            if app and (
                app.dashboard_selected
                or app.pip_selected
                or app.media_view_selected
                or self.active_view is not None
            ):
                return None
            if app and app.logical_input is not None:
                return app.logical_input
        return (
            await self.display.async_get_input(use_cache=use_cache)
            if self.ready
            else None
        )

    async def async_get_signal_status(self):
        if (
            self.dashboard_active
            or self.pip_active
            or self.media_view_active
            or self.active_view is not None
        ):
            return None
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
            app = self.hass.data[DOMAIN][self.entry_id].get("display_app")
            if app and method == "async_set_input":
                if await app.async_select_hdmi(args[0]):
                    controller._current_input_id = args[0]
                    controller._source = controller._resolve_source_name(args[0])
                    controller.async_write_ha_state()
                    return True
                app.saved.pop("dashboard", None)
                app.saved.pop("pip", None)
                app.saved.pop("media_view", None)
                app.saved.pop("custom_view", None)
                await app.async_pause_resident(leave=False)
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
            app = self.hass.data[DOMAIN][self.entry_id].get("display_app")
            if app and app.resident_connected:
                await app.async_pause_resident()
                app.saved["resume_after_external"] = True
                await app.store.async_save(app.saved)
            token = secrets.token_hex(16)
            controller.external_owner = token
            return token

    async def async_end_external_presentation(self, token):
        if self.ready and self.controller.external_owner == token:
            self.controller.external_owner = None
            app = self.hass.data[DOMAIN][self.entry_id].get("display_app")
            if app and app.saved.pop("resume_after_external", False):
                await app.async_resume()

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
