"""Pure LG display entity and native LG actions."""

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature as Feature,
    MediaPlayerDeviceClass,
    MediaPlayerState,
)
from homeassistant.core import SupportsResponse
from homeassistant.helpers.entity_platform import async_get_current_platform
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
import voluptuous as vol
from .const import DOMAIN, INPUT_SOURCES


async def async_setup_entry(hass, entry, async_add_entities):
    controller = hass.data[DOMAIN][entry.entry_id]["controller"]
    player = LGDisplayMediaPlayer(controller, entry)
    hass.data[DOMAIN][entry.entry_id]["media_player"] = player
    async_add_entities([player])
    services = {
        "show_view": (
            {
                vol.Required("view"): vol.All(cv.string, vol.Length(min=1, max=80)),
                vol.Optional("transition", default="none"): vol.In(["none", "smooth"]),
                vol.Optional("duration", default=0): vol.All(
                    cv.positive_int, vol.Range(min=0, max=3600)
                ),
            },
            "async_show_view",
        ),
        "show_display_app": (
            {
                vol.Optional("title", default="Home Assistant"): vol.All(
                    cv.string, vol.Length(min=1, max=160)
                ),
                vol.Optional("message", default=""): vol.All(
                    cv.string, vol.Length(max=2000)
                ),
                vol.Optional("duration", default=30): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=3600)
                ),
                vol.Optional("dashboard", default=False): cv.boolean,
                vol.Optional("layout", default="fullscreen"): vol.In(
                    ["fullscreen", "overlay", "pip"]
                ),
                vol.Optional("priority", default="normal"): vol.In(
                    ["normal", "urgent"]
                ),
            },
            "async_show_display_app",
        ),
        "send_remote_command": (
            {
                vol.Required("command"): vol.In(
                    [
                        "up",
                        "down",
                        "left",
                        "right",
                        "select",
                        "menu",
                        "home",
                        "information",
                        "back",
                        "exit",
                    ]
                )
            },
            "async_send_remote_command",
        ),
        "show_toast": (
            {
                vol.Required("message"): vol.All(
                    cv.string, vol.Length(min=1, max=1000)
                ),
                vol.Optional("priority", default="normal"): vol.In(
                    ["normal", "urgent"]
                ),
            },
            "async_show_toast",
        ),
        "show_native_image": (
            {
                vol.Required("media_id"): cv.string,
                vol.Optional("duration", default=10): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=3600)
                ),
                vol.Optional("priority", default="normal"): vol.In(
                    ["normal", "urgent"]
                ),
            },
            "async_show_native_image",
        ),
        "show_native_video": (
            {
                vol.Required("media_id"): cv.string,
                vol.Optional("duration", default=60): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=3600)
                ),
                vol.Optional("priority", default="normal"): vol.In(
                    ["normal", "urgent"]
                ),
            },
            "async_show_native_video",
        ),
        "show_website": (
            {
                vol.Required("url"): cv.string,
                vol.Optional("duration", default=60): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=3600)
                ),
                vol.Optional("priority", default="normal"): vol.In(
                    ["normal", "urgent"]
                ),
            },
            "async_show_website",
        ),
        "show_stream": (
            {
                vol.Required("media_id"): cv.string,
                vol.Optional("muted", default=True): cv.boolean,
                vol.Optional("duration", default=300): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=3600)
                ),
                vol.Optional("priority", default="normal"): vol.In(
                    ["normal", "urgent"]
                ),
            },
            "async_show_stream",
        ),
        "prepare_boot_image": (
            {
                vol.Required("media_id"): cv.string,
                vol.Optional("media_directory", default="local"): cv.string,
            },
            "async_prepare_boot_image",
        ),
        "clear_content": ({}, "async_clear_content"),
    }
    platform = async_get_current_platform()
    for name, (schema, method) in services.items():
        platform.async_register_entity_service(
            name,
            schema,
            method,
            supports_response=SupportsResponse.ONLY
            if name == "prepare_boot_image"
            else SupportsResponse.NONE,
        )


class LGDisplayMediaPlayer(MediaPlayerEntity):
    _attr_has_entity_name = True
    _attr_name = "Display"
    _attr_should_poll = False
    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_supported_features = (
        Feature.TURN_ON
        | Feature.TURN_OFF
        | Feature.SELECT_SOURCE
        | Feature.VOLUME_SET
        | Feature.VOLUME_STEP
        | Feature.VOLUME_MUTE
        | Feature.PLAY_MEDIA
    )

    def __init__(self, controller, entry):
        self.controller = controller
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_media_player"

    @property
    def device_info(self):
        display = self.controller._lg_display
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": self.entry.title,
            "manufacturer": "LG",
            "model": display.model_name or "Professional Display",
            "sw_version": display.software_version,
        }

    @property
    def available(self):
        return (
            self.controller._lg_display.is_available
            or self.controller._lg_display.is_intentionally_unpowered
        )

    @property
    def state(self):
        if self.controller._lg_display.is_intentionally_unpowered:
            return MediaPlayerState.OFF
        return (
            MediaPlayerState.ON
            if self.controller.power is True
            else MediaPlayerState.OFF
            if self.controller.power is False
            else None
        )

    @property
    def display_app(self):
        return (
            self.controller.hass.data.get(DOMAIN, {})
            .get(self.entry.entry_id, {})
            .get("display_app")
        )

    @property
    def hdmi_source(self):
        """Physical input retained behind any persistent Studio view."""
        app = self.display_app
        input_id = app.logical_input if app else None
        if input_id is None:
            input_id = self.controller._current_input_id
        for index in range(1, 4):
            if input_id == INPUT_SOURCES[f"HDMI {index}"]:
                return self.entry.options.get(
                    f"input_name_hdmi{index}", f"HDMI {index}"
                )
        return None

    @property
    def dashboard_source(self):
        return self._app_source_name("Dashboard")

    @property
    def pip_source(self):
        return self._app_source_name("Dashboard PiP")

    @property
    def media_view_source(self):
        return self._app_source_name("Mediaplayer")

    def _app_source_name(self, name):
        labels = {
            self.entry.options.get(f"input_name_hdmi{i}", f"HDMI {i}")
            for i in range(1, 4)
        }
        while name in labels:
            name += " (App)"
        return name

    @property
    def app_view_sources(self):
        from .layout_library import SOURCE_VIEWS, source_names

        views = getattr(self.display_app, "view_sources", None)
        if not isinstance(views, dict):
            views = SOURCE_VIEWS
        return source_names(
            views,
            [
                self.entry.options.get(f"input_name_hdmi{i}", f"HDMI {i}")
                for i in range(1, 4)
            ],
        )

    @property
    def source(self):
        app = self.display_app
        selected = getattr(app, "selected_view", None)
        if (
            isinstance(selected, str)
            and selected in self.app_view_sources
            and app.resident_connected
        ):
            return self.app_view_sources[selected]
        if app and app.dashboard_selected and app.resident_connected:
            return self.dashboard_source
        if app and app.pip_selected and app.resident_connected:
            return self.pip_source
        if app and app.media_view_selected and app.resident_connected:
            return self.media_view_source
        if (
            self.controller._source in self.app_view_sources.values()
            and app
            and not app.dashboard_selected
            and not app.pip_selected
            and not app.media_view_selected
        ):
            return self.controller._resolve_source_name(app.selected_input)
        return self.controller._source

    @property
    def source_list(self):
        sources = [
            self.entry.options.get(f"input_name_hdmi{i}", f"HDMI {i}")
            for i in range(1, 4)
            if self.entry.options.get(f"show_input_hdmi{i}", True)
        ]
        if self.display_app and self.display_app.dashboard_available:
            sources.extend(list(self.app_view_sources.values()))
        return sources

    @property
    def volume_level(self):
        return (
            self.controller.volume / 100 if self.controller.volume is not None else None
        )

    @property
    def is_volume_muted(self):
        return self.controller.muted

    @property
    def extra_state_attributes(self):
        return {
            "integration_domain": DOMAIN,
            "native_web_enabled": self.entry.options.get("native_web_enabled", False),
            "display_app_enabled": self.entry.options.get("display_app_enabled", False),
            "display_app_mode": self.entry.options.get("display_app_mode", "si"),
            "display_app_resident": self.entry.options.get(
                "display_app_resident", False
            ),
            "presentation_active": self.controller.presentation_active,
            "presentation_queue_size": len(self.controller._presentation_queue),
            "presentation_error": self.controller._presentation_error,
            "osd_restore_error": self.controller._lg_display.osd_restore_error,
            "signal_present": self.controller.signal,
            "hdmi_source": self.hdmi_source,
            "view_sources": self.app_view_sources
            if self.display_app and self.display_app.dashboard_available
            else {},
            "selected_view": getattr(self.display_app, "selected_view", None),
            "dashboard_source": self.dashboard_source
            if self.display_app and self.display_app.dashboard_available
            else None,
            "media_view_source": self.media_view_source
            if self.display_app and self.display_app.dashboard_available
            else None,
            "pip_source": self.pip_source
            if self.display_app and self.display_app.dashboard_available
            else None,
        }

    async def async_added_to_hass(self):
        self.controller.entity_id = self.entity_id
        self.async_on_remove(
            self.hass.bus.async_listen(
                "homekit_tv_remote_key_pressed", self._async_homekit_key
            )
        )
        self.async_on_remove(self.controller.subscribe(self.async_write_ha_state))

    async def _async_homekit_key(self, event):
        if event.data.get("entity_id") != self.entity_id:
            return
        commands = {
            "arrow_up": "up",
            "arrow_down": "down",
            "arrow_left": "left",
            "arrow_right": "right",
            "select": "select",
            "back": "back",
            "exit": "home",
            "information": "information",
        }
        if command := commands.get(event.data.get("key_name")):
            await self.async_send_remote_command(command)

    async def async_turn_on(self):
        await self.controller.async_turn_on()

    async def async_turn_off(self):
        await self.controller.async_turn_off()

    async def async_show_view(self, view, transition="none", duration=0):
        """Display a saved Studio view, optionally animating its HDMI geometry."""
        await self.controller.async_select_app_view(
            view, transition=transition, duration=duration
        )

    async def async_select_source(self, source):
        if (
            source == self.media_view_source
            and self.display_app
            and self.display_app.dashboard_available
        ):
            await self.controller.async_select_media_view()
            return
        if (
            source == self.pip_source
            and self.display_app
            and self.display_app.dashboard_available
        ):
            await self.controller.async_select_pip()
            return
        if (
            source == self.dashboard_source
            and self.display_app
            and self.display_app.dashboard_available
        ):
            await self.controller.async_select_dashboard()
            return
        if self.display_app and self.display_app.dashboard_available:
            for view_id, name in self.app_view_sources.items():
                if source == name:
                    await self.controller.async_select_app_view(view_id)
                    return
        for i in range(1, 4):
            if source == self.entry.options.get(f"input_name_hdmi{i}", f"HDMI {i}"):
                await self.controller.async_select_input(INPUT_SOURCES[f"HDMI {i}"])
                return
        raise HomeAssistantError("Unknown LG input")

    async def async_set_volume_level(self, volume):
        if not await self.controller._lg_display.async_set_volume(
            round(max(0, min(1, volume)) * 100)
        ):
            raise HomeAssistantError("LG rejected volume")
        await self.controller.async_refresh()

    async def async_volume_up(self):
        await self.controller._lg_display.async_volume_up_step()
        await self.controller.async_refresh()

    async def async_volume_down(self):
        await self.controller._lg_display.async_volume_down_step()
        await self.controller.async_refresh()

    async def async_mute_volume(self, mute):
        if (
            await self.controller._lg_display.async_send_command(
                "k", "e", 0 if mute else 1
            )
            is None
        ):
            raise HomeAssistantError("LG rejected mute")
        await self.controller.async_refresh()

    async def async_send_remote_command(self, command):
        keys = {
            "up": 0x40,
            "down": 0x41,
            "left": 0x07,
            "right": 0x06,
            "select": 0x44,
            "back": 0x28,
            "menu": 0x43,
            "home": 0x7C,
            "exit": 0x5B,
            "information": 0xAA,
        }
        if command not in keys:
            raise HomeAssistantError("Unsupported LG navigation key")
        if not await self.controller._lg_display.async_send_remote_key(keys[command]):
            raise HomeAssistantError("LG rejected the remote command")

    async def async_play_media(self, media_type, media_id, **kwargs):
        duration = kwargs.get("extra", {}).get("duration", 60)
        if type(duration) is not int or not 1 <= duration <= 3600:
            raise HomeAssistantError("Duration must be 1–3600 seconds")
        if media_type in {"url", "website"}:
            await self.controller.async_show_website(media_id, duration)
        elif media_type in {
            "hls",
            "application/vnd.apple.mpegurl",
            "application/x-mpegURL",
        }:
            await self.controller.async_show_stream(media_id, duration)
        elif media_type == "image" or media_type.startswith("image/"):
            await self.controller.async_show_native_image(media_id, duration)
        elif media_type == "video" or media_type.startswith("video/"):
            await self.controller.async_show_native_video(media_id, duration)
        else:
            raise HomeAssistantError("Unsupported native media type")

    async def async_show_toast(self, **kwargs):
        return await self.controller.async_show_toast(**kwargs)

    async def async_show_display_app(self, **kwargs):
        return await self.controller.async_show_display_app(**kwargs)

    async def async_show_native_image(self, **kwargs):
        return await self.controller.async_show_native_image(**kwargs)

    async def async_show_native_video(self, **kwargs):
        return await self.controller.async_show_native_video(**kwargs)

    async def async_show_website(self, **kwargs):
        return await self.controller.async_show_website(**kwargs)

    async def async_show_stream(self, **kwargs):
        return await self.controller.async_show_stream(**kwargs)

    async def async_prepare_boot_image(self, **kwargs):
        return await self.controller.async_prepare_boot_image(**kwargs)

    async def async_clear_content(self, **kwargs):
        return await self.controller.async_clear_content(**kwargs)
