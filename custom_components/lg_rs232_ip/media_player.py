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
    def source(self):
        return self.controller._source

    @property
    def source_list(self):
        return [
            self.entry.options.get(f"input_name_hdmi{i}", f"HDMI {i}")
            for i in range(1, 4)
            if self.entry.options.get(f"show_input_hdmi{i}", True)
        ]

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
            "presentation_active": self.controller.presentation_active,
            "presentation_queue_size": len(self.controller._presentation_queue),
            "presentation_error": self.controller._presentation_error,
            "signal_present": self.controller.signal,
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

    async def async_select_source(self, source):
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
            "menu": 0x28,
            "home": 0x43,
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
