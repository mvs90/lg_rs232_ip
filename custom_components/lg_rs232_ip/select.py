"""Select platform for LG Display RS232/IP integration."""

import logging
from contextlib import nullcontext
from datetime import timedelta
from typing import Optional

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    ENERGY_SAVING_MODES,
    INPUT_SOURCES,
    OSD_LANGUAGES,
    PICTURE_MODES,
    SOUND_MODES,
)
from .lg_display import LGDisplay
from .system_settings import SystemSettingEntity
from .maintenance import MaintenanceEntity, REPEATS, DURATIONS
from .picture_settings import PictureSettingEntity, NATIVE_OPTIONS
from .power_settings import POWER_SETTINGS, PowerSettingEntity, remote_power_on_status
from .layout_library import source_names
from .device_profile import (
    ASPECT_RATIOS,
    DPM_DELAYS,
    SIGNAGE_PICTURE_MODES,
    ISM_DESCRIPTIONS,
    ism_methods,
    is_uh5f,
)
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)


class LGDisplayBaseSelect(SelectEntity):
    """Base select entity with cleaner Home Assistant device-view naming."""

    _attr_entity_registry_enabled_default = False
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities for LG Display."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    lg_display = data["lg_display"]

    entities = [
        LGDisplayInputSelect(
            lg_display,
            data["name"],
            config_entry.entry_id,
        ),
        LGDisplayPictureModeSelect(
            lg_display,
            data["name"],
            config_entry.entry_id,
            data.get("picture_settings"),
        ),
        LGDisplayEnergySavingSelect(
            lg_display,
            data["name"],
            config_entry.entry_id,
        ),
        LGDisplaySoundModeSelect(
            lg_display,
            data["name"],
            config_entry.entry_id,
        ),
        LGDisplayOSDLanguageSelect(
            lg_display,
            data["name"],
            config_entry.entry_id,
        ),
    ]

    entities.append(
        LGDisplayAspectRatioSelect(lg_display, data["name"], config_entry.entry_id)
    )
    entities.append(
        LGDisplayDpmDelaySelect(lg_display, data["name"], config_entry.entry_id)
    )
    entities.append(
        LGDisplayIsmMethodSelect(lg_display, data["name"], config_entry.entry_id, data.get("maintenance"))
    )
    if settings := data.get("system_settings"):
        entities.append(SystemTemperatureUnit(settings))

    if maintenance := data.get("maintenance"):
        entities.extend([IsmSettingSelect(maintenance, "ismTimer", "ism_repeat"), IsmSettingSelect(maintenance, "ismTime", "ism_duration")])

    if picture := data.get("picture_settings"):
        entities.extend(PictureOptionSelect(picture, key) for key in ("gamma", "black_level", "hdr_picture_mode"))
        if picture.web and is_uh5f(lg_display.model_name):
            entities.extend(PictureOptionSelect(picture, key) for key in NATIVE_OPTIONS)

    if power := data.get("power_settings"):
        entities.extend(PowerSettingsSelect(power, key) for key in (
            "pm_mode", "power_on_status", "dpm_wake_up"))

    async_add_entities(entities)


class IsmSettingSelect(MaintenanceEntity, SelectEntity):
    def __init__(self, coordinator, key, translation_key):
        super().__init__(coordinator, key, translation_key, "mdi:monitor-shimmer")
        self._choices = REPEATS if key == "ismTimer" else {v: v for v in DURATIONS}

    @property
    def options(self):
        return list(self._choices)

    @property
    def current_option(self):
        value = (self.coordinator.data or {}).get(self.key)
        return next((k for k, v in self._choices.items() if v == value), None)

    async def async_select_option(self, option):
        if option not in self._choices:
            raise HomeAssistantError("Unsupported ISM option")
        await self.coordinator.async_set(self.key, self._choices[option])


class PictureOptionSelect(PictureSettingEntity, SelectEntity):
    @property
    def options(self):
        return self.coordinator.options_for(self.key)

    @property
    def current_option(self):
        return (self.coordinator.data or {}).get(self.key)

    async def async_select_option(self, option):
        await self.coordinator.async_set(self.key, option)


class LGDisplayInputSelect(LGDisplayBaseSelect):
    """Explicit native and resident-app sources, including saved Studio views."""

    _attr_entity_registry_enabled_default = True
    _attr_icon = "mdi:input-hdmi"
    _attr_name = "Input"

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        self._lg_display = lg_display
        self._entry_id = unique_id
        self._attr_unique_id = f"{unique_id}_input"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, unique_id)})
        self._input_id = None

    @property
    def _data(self):
        return (
            self.hass.data.get(DOMAIN, {}).get(self._entry_id, {})
            if getattr(self, "hass", None)
            else {}
        )

    @property
    def _sources(self):
        sources = {label: ("native", code) for label, code in INPUT_SOURCES.items()}
        app = self._data.get("display_app")
        if app and app.resident:
            sources.update(
                {
                    f"App-{label}": ("hdmi", code)
                    for label, code in INPUT_SOURCES.items()
                }
            )
            if app.dashboard_available:
                sources.update(
                    {
                        f"App-{name}": ("view", key)
                        for key, name in source_names(
                            app.view_sources, INPUT_SOURCES
                        ).items()
                    }
                )
        return sources

    @property
    def options(self) -> list[str]:
        return list(self._sources)

    @property
    def current_option(self) -> Optional[str]:
        app = self._data.get("display_app")
        if app and app.resident_connected:
            target = (
                ("view", app.selected_view)
                if app.selected_view
                else ("hdmi", app.selected_input)
            )
        else:
            target = ("native", self._input_id)
        return next(
            (name for name, value in self._sources.items() if value == target), None
        )

    @property
    def available(self) -> bool:
        return self._lg_display.is_available

    async def async_added_to_hass(self) -> None:
        if controller := self._data.get("controller"):
            self.async_on_remove(controller.subscribe(self._controller_changed))
        await self.async_update()

    def _controller_changed(self):
        controller = self._data.get("controller")
        if controller and controller.power is True:
            self._input_id = controller._current_input_id
        # App acknowledgements and Studio edits update this state without extra TCP I/O.
        self.async_write_ha_state()

    async def async_update(self) -> None:
        if await self._lg_display.async_get_power_status() is True:
            self._input_id = await self._lg_display.async_get_input()

    async def async_select_option(self, option: str) -> None:
        source = self._sources.get(option)
        if source is None:
            raise HomeAssistantError("Unknown LG input")
        controller = self._data["controller"]
        kind, value = source
        if kind == "view":
            await controller.async_select_app_view(value)
        else:
            await controller.async_select_input(value, via_app=kind == "hdmi")
            self._input_id = controller._current_input_id
        self.async_write_ha_state()


class LGDisplayIsmMethodSelect(LGDisplayBaseSelect):
    """Named image-retention treatments instead of arbitrary protocol bytes."""

    _attr_entity_registry_enabled_default = True
    _attr_translation_key = "ism_method"
    _attr_icon = "mdi:monitor-shimmer"

    def __init__(self, display, name, unique_id, maintenance=None):
        self._lg_display = display
        self._maintenance = maintenance
        self._attr_unique_id = f"{unique_id}_ism_method"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, unique_id)})
        self._value = None

    @property
    def options(self):
        return list(ism_methods(self._lg_display.model_name))

    @property
    def current_option(self):
        return next(
            (
                key
                for key, code in ism_methods(self._lg_display.model_name).items()
                if code == self._value
            ),
            None,
        )

    @property
    def available(self):
        return self._lg_display.is_available and self.current_option is not None

    @property
    def extra_state_attributes(self):
        return {
            "mode_description": ISM_DESCRIPTIONS.get(self.current_option),
            "protocol_code": f"0x{self._value:02x}"
            if self._value is not None
            else None,
            "model_profile": "UH5F-H"
            if is_uh5f(self._lg_display.model_name)
            else "Generic Signage (model-dependent)",
        }

    async def async_update(self):
        self._value = None
        if await self._lg_display.async_get_power_status() is True:
            self._value = await self._lg_display.async_get_ism_method()

    async def async_select_option(self, option):
        async with self._maintenance._settings_lock if self._maintenance else nullcontext():
            async with self._maintenance.controller._control_lock if self._maintenance else nullcontext():
                await self._async_select_mode(option)
        if self._maintenance:
            await self._maintenance.async_request_refresh()

    async def _async_select_mode(self, option):
        modes = ism_methods(self._lg_display.model_name)
        if option not in modes:
            raise HomeAssistantError("Unsupported ISM method for this display profile")
        if await self._lg_display.async_get_power_status() is not True:
            raise HomeAssistantError("Display must be on to change ISM method")
        if not await self._lg_display.async_set_ism_method(modes[option]):
            await self.async_update()
            self.async_write_ha_state()
            raise HomeAssistantError(
                "Display did not confirm ISM method; check model support, ISM schedule and imported media on the LG"
            )
        self._value = modes[option]
        self.async_write_ha_state()



class LGDisplayPictureModeSelect(LGDisplayBaseSelect):
    """Picture mode selection for LG Display."""

    _attr_entity_registry_enabled_default = True
    _attr_translation_key = "picture_mode"

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str, picture=None) -> None:
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._current_mode: Optional[str] = None
        self._picture = picture
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, unique_id)})

    @property
    def _modes(self):
        return (
            SIGNAGE_PICTURE_MODES
            if is_uh5f(self._lg_display.model_name)
            else PICTURE_MODES
        )

    @property
    def unique_id(self) -> str:
        return f"{self._unique_id}_picture_mode"

    @property
    def options(self) -> list[str]:
        return list(self._modes.keys())

    @property
    def current_option(self) -> Optional[str]:
        return self._current_mode

    @property
    def available(self) -> bool:
        return self._lg_display.is_available and self._current_mode is not None

    @property
    def icon(self) -> str:
        return "mdi:television"

    async def async_added_to_hass(self) -> None:
        await self.async_update()

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is not True:
            self._current_mode = None
            return

        mode_value = await self._lg_display.async_get_picture_mode()
        self._current_mode = next(
            (name for name, value in self._modes.items() if value == mode_value), None
        )

    async def async_select_option(self, option: str) -> None:
        async with self._picture._settings_lock if self._picture else nullcontext():
            async with self._picture.controller._control_lock if self._picture else nullcontext():
                await self._async_select_picture_mode(option)
        if self._picture:
            await self._picture.async_request_refresh()

    async def _async_select_picture_mode(self, option):
        if option not in self._modes:
            raise HomeAssistantError("Unsupported picture mode")
        if await self._lg_display.async_get_power_status() is not True:
            raise HomeAssistantError("Display must be on to change picture mode")
        if not await self._lg_display.async_set_picture_mode(self._modes[option]):
            await self.async_update()
            self.async_write_ha_state()
            raise HomeAssistantError(
                "Display did not confirm picture mode in the current input/mode"
            )
        self._current_mode = option
        self.async_write_ha_state()


class LGDisplayEnergySavingSelect(LGDisplayBaseSelect):
    """Energy saving mode selection for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._current_mode: Optional[str] = None

    @property
    def unique_id(self) -> str:
        return f"{self._unique_id}_energy_saving"

    @property
    def name(self) -> str:
        return "Energy Saving"

    @property
    def options(self) -> list[str]:
        return list(ENERGY_SAVING_MODES.keys())

    @property
    def current_option(self) -> Optional[str]:
        return self._current_mode

    @property
    def available(self) -> bool:
        return self._lg_display.is_available

    @property
    def icon(self) -> str:
        return "mdi:leaf"

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
        }

    async def async_added_to_hass(self) -> None:
        await self.async_update()

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        mode_value = await self._lg_display.async_get_energy_saving()
        if mode_value is None:
            return

        for name, value in ENERGY_SAVING_MODES.items():
            if value == mode_value:
                self._current_mode = name
                return

        self._current_mode = f"0x{mode_value:02x}"

    async def async_select_option(self, option: str) -> None:
        if option not in ENERGY_SAVING_MODES:
            raise HomeAssistantError("Unsupported energy saving")
        if await self._lg_display.async_get_power_status() is not True:
            raise HomeAssistantError("Display must be on to change energy saving")
        if not await self._lg_display.async_set_energy_saving(
            ENERGY_SAVING_MODES[option]
        ):
            await self.async_update()
            self.async_write_ha_state()
            raise HomeAssistantError(
                "Display did not confirm energy saving in the current input/mode"
            )
        self._current_mode = option
        self.async_write_ha_state()


class LGDisplaySoundModeSelect(LGDisplayBaseSelect):
    """Sound mode selection for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._current_mode: Optional[str] = None

    @property
    def unique_id(self) -> str:
        return f"{self._unique_id}_sound_mode"

    @property
    def name(self) -> str:
        return "Sound Mode"

    @property
    def options(self) -> list[str]:
        return list(SOUND_MODES.keys())

    @property
    def current_option(self) -> Optional[str]:
        return self._current_mode

    @property
    def available(self) -> bool:
        return self._lg_display.is_available

    @property
    def icon(self) -> str:
        return "mdi:volume-high"

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
        }

    async def async_added_to_hass(self) -> None:
        await self.async_update()

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        mode_value = await self._lg_display.async_get_sound_mode()
        if mode_value is None:
            return

        for name, value in SOUND_MODES.items():
            if value == mode_value:
                self._current_mode = name
                return

        self._current_mode = f"0x{mode_value:02x}"

    async def async_select_option(self, option: str) -> None:
        if option not in SOUND_MODES:
            _LOGGER.warning("Attempted to select unsupported sound mode: %s", option)
            return

        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            _LOGGER.info("Display is off; ignoring sound mode change %s", option)
            return

        if await self._lg_display.async_set_sound_mode(SOUND_MODES[option]):
            self._current_mode = option
            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to set sound mode to %s", option)


class LGDisplayOSDLanguageSelect(LGDisplayBaseSelect):
    """OSD language selection for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._current_language: Optional[str] = None
        self._language_to_code = {label: code for code, label in OSD_LANGUAGES.items()}

    @property
    def unique_id(self) -> str:
        return f"{self._unique_id}_osd_language"

    @property
    def name(self) -> str:
        return "OSD Language"

    @property
    def options(self) -> list[str]:
        return list(self._language_to_code.keys())

    @property
    def current_option(self) -> Optional[str]:
        return self._current_language

    @property
    def available(self) -> bool:
        return self._lg_display.is_available

    @property
    def icon(self) -> str:
        return "mdi:translate"

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
        }

    async def async_added_to_hass(self) -> None:
        await self.async_update()

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        language_code = await self._lg_display.async_get_osd_language()
        if language_code is None:
            return

        self._current_language = OSD_LANGUAGES.get(
            language_code, f"0x{language_code:02x}"
        )

    async def async_select_option(self, option: str) -> None:
        if option not in self._language_to_code:
            _LOGGER.warning("Attempted to select unsupported OSD language: %s", option)
            return

        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            _LOGGER.info("Display is off; ignoring OSD language change %s", option)
            return

        if await self._lg_display.async_set_osd_language(
            self._language_to_code[option]
        ):
            self._current_language = option
            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to set OSD language to %s", option)


class LGDisplayDpmDelaySelect(LGDisplayBaseSelect):
    """Hardware DPM timeout; the legacy switch enables the one-minute setting."""

    def __init__(self, display, name, unique_id):
        self._lg_display = display
        self._attr_name = "DPM Delay"
        self._attr_unique_id = f"{unique_id}_dpm_delay"
        self._attr_options = list(DPM_DELAYS)
        self._attr_current_option = None
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, unique_id)})

    @property
    def available(self):
        return self._lg_display.is_available and self._attr_current_option is not None

    async def async_update(self):
        result = await self._lg_display.async_send_command("f", "j", 0xFF)
        self._attr_current_option = next(
            (k for k, v in DPM_DELAYS.items() if v == result), None
        )

    async def async_select_option(self, option):
        if option not in DPM_DELAYS:
            raise HomeAssistantError("Unsupported DPM timeout")
        value = DPM_DELAYS[option]
        result = await self._lg_display.async_send_command("f", "j", value)
        if result != value:
            raise HomeAssistantError("Display did not confirm the DPM timeout")
        self._attr_current_option = option
        self.async_write_ha_state()


class LGDisplayAspectRatioSelect(LGDisplayBaseSelect):
    """Documented aspect ratios, mirrored to the resident HDMI video plane."""

    _attr_entity_registry_enabled_default = True
    _attr_icon = "mdi:aspect-ratio"

    def __init__(self, display, name, unique_id):
        self._lg_display = display
        self._attr_name = "Aspect Ratio"
        self._attr_unique_id = f"{unique_id}_aspect_ratio"
        self._attr_options = list(ASPECT_RATIOS)
        self._attr_current_option = None
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, unique_id)})

    @property
    def available(self):
        return self._lg_display.is_available and self._attr_current_option is not None

    async def async_added_to_hass(self):
        self.async_on_remove(
            self._lg_display.subscribe_picture_settings(
                lambda: self.async_schedule_update_ha_state(force_refresh=True)
            )
        )
        await self.async_update()

    async def async_update(self):
        value = None
        if await self._lg_display.async_get_power_status() is True:
            value = await self._lg_display.async_get_aspect_ratio()
        self._attr_current_option = next(
            (k for k, v in ASPECT_RATIOS.items() if v == value), None
        )

    async def async_select_option(self, option):
        if option not in ASPECT_RATIOS:
            raise HomeAssistantError("Unsupported aspect ratio")
        if await self._lg_display.async_get_power_status() is not True:
            raise HomeAssistantError("Display must be on to change aspect ratio")
        if not await self._lg_display.async_set_aspect_ratio(ASPECT_RATIOS[option]):
            await self.async_update()
            self.async_write_ha_state()
            raise HomeAssistantError(
                "Display did not confirm aspect ratio in the current input/mode"
            )
        self._attr_current_option = option
        self.async_write_ha_state()




class SystemTemperatureUnit(SystemSettingEntity, SelectEntity):
    _attr_options = ["celsius", "fahrenheit"]

    def __init__(self, settings):
        super().__init__(settings, "temperatureUnit", "display_temperature_unit", "mdi:temperature-celsius")

    @property
    def current_option(self):
        return (self.coordinator.data or {}).get(self.key)

    async def async_select_option(self, option):
        await self.coordinator.async_set(self.key, option)


class PowerSettingsSelect(PowerSettingEntity, SelectEntity):
    def __init__(self, coordinator, key):
        super().__init__(coordinator, key, "mdi:power-settings")
        self._attr_options = list(POWER_SETTINGS[key].options)

    @property
    def current_option(self):
        return (self.coordinator.data or {}).get(self.key)

    @property
    def extra_state_attributes(self):
        if self.key == "pm_mode":
            return {"remote_power_on": remote_power_on_status(self.coordinator.data or {})}
        return None

    async def async_select_option(self, option):
        await self.coordinator.async_set(self.key, option)
