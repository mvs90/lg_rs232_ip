"""Select platform for LG Display RS232/IP integration."""

import logging
import time
from datetime import timedelta
from typing import Dict, Optional

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    ENERGY_SAVING_MODES,
    INPUT_DETECTION_CANDIDATES,
    INPUT_SOURCES,
    OSD_LANGUAGES,
    PICTURE_MODES,
    SOUND_MODES,
)
from .lg_display import LGDisplay
from .device_profile import DPM_DELAYS, SIGNAGE_PICTURE_MODES, is_uh5f
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
        LGDisplayDpmDelaySelect(lg_display, data["name"], config_entry.entry_id)
    )
    async_add_entities(entities)


class LGDisplayInputSelect(LGDisplayBaseSelect):
    """Input selection for LG Display."""

    _attr_entity_registry_enabled_default = True

    def __init__(
        self,
        lg_display: LGDisplay,
        name: str,
        unique_id: str,
    ) -> None:
        """Initialize the select entity."""
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._supported_inputs: Dict[str, int] = {
            label: value for label, value in INPUT_SOURCES.items()
        }
        self._current_input: Optional[str] = None
        self._pending_input: Optional[str] = None
        self._pending_until: float = 0.0
        self._detection_done = False

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._unique_id}_input"

    @property
    def name(self) -> str:
        """Return the name."""
        return "Input"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the LG display."""
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
        }

    @property
    def current_option(self) -> Optional[str]:
        """Return the current selected option."""
        if self._current_input is None:
            return "unknown"
        return self._current_input

    @property
    def options(self) -> list[str]:
        """Return available options."""
        return list(self._supported_inputs.keys())

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self._lg_display.is_available

    @property
    def scan_interval(self) -> int:
        """Return the scan interval in seconds."""
        return 5  # Update every 5 seconds for faster status changes

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:input-hdmi"

    async def async_added_to_hass(self) -> None:
        """Run setup when entity is added."""
        await self.async_update()

    async def async_update(self) -> None:
        """Update current input from the display."""
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            _LOGGER.debug("Display is off; keeping input state unchanged")
            return

        input_id = await self._lg_display.async_get_input()
        now = time.monotonic()
        if input_id is None:
            if self._pending_input and now < self._pending_until:
                _LOGGER.debug(
                    "Keeping pending input %s until display confirms it",
                    self._pending_input,
                )
                self._current_input = self._pending_input
                return
            _LOGGER.debug(
                "LG Display input query returned no value; keeping last known input"
            )
            self._pending_input = None
            if self._current_input is None:
                self._current_input = "unknown"
            return

        actual_label = None
        for label, candidate in self._supported_inputs.items():
            if candidate == input_id:
                actual_label = label
                break

        if self._pending_input and now < self._pending_until:
            if actual_label == self._pending_input:
                self._pending_input = None
                self._pending_until = 0.0
                self._current_input = actual_label
                return

            _LOGGER.debug(
                "Keeping pending input %s until display confirms it",
                self._pending_input,
            )
            self._current_input = self._pending_input
            return

        if actual_label:
            self._pending_input = None
            self._pending_until = 0.0
            self._current_input = actual_label
            return

        # If we get an input code we don't know yet, try to detect it
        _LOGGER.debug(
            "LG Display input returned unknown value 0x%02x, attempting detection",
            input_id,
        )

        # Try to match this unknown code with known inputs by testing each one
        for label in self._supported_inputs.keys():
            candidates = INPUT_DETECTION_CANDIDATES.get(
                label, [self._supported_inputs.get(label)]
            )
            if input_id in candidates:
                # Found a match! Update the mapping
                self._supported_inputs[label] = input_id
                self._current_input = label
                _LOGGER.info("Detected input %s uses code 0x%02x", label, input_id)
                return

        # Still unknown, display as hex value
        self._pending_input = None
        self._current_input = f"0x{input_id:02x}"
        _LOGGER.debug("LG Display input 0x%02x could not be identified", input_id)

    async def async_select_option(self, option: str) -> None:
        input_id = self._supported_inputs.get(option)
        if input_id is None:
            raise HomeAssistantError("Unknown LG input")
        controller = self.hass.data[DOMAIN][self._unique_id]["controller"]
        await controller.async_select_input(input_id)
        self._current_input = option
        self.async_write_ha_state()


class LGDisplayPictureModeSelect(LGDisplayBaseSelect):
    """Picture mode selection for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._current_mode: Optional[str] = None

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
    def name(self) -> str:
        return "Picture Mode"

    @property
    def options(self) -> list[str]:
        return list(self._modes.keys())

    @property
    def current_option(self) -> Optional[str]:
        return self._current_mode

    @property
    def available(self) -> bool:
        return self._lg_display.is_available

    @property
    def icon(self) -> str:
        return "mdi:television"

    async def async_added_to_hass(self) -> None:
        await self.async_update()

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        mode_value = await self._lg_display.async_get_picture_mode()
        if mode_value is None:
            return

        for name, value in self._modes.items():
            if value == mode_value:
                self._current_mode = name
                return

        self._current_mode = f"0x{mode_value:02x}"

    async def async_select_option(self, option: str) -> None:
        if option not in self._modes:
            _LOGGER.warning("Attempted to select unsupported picture mode: %s", option)
            return

        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            _LOGGER.info("Display is off; ignoring picture mode change %s", option)
            return

        if await self._lg_display.async_set_picture_mode(self._modes[option]):
            self._current_mode = option
            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to set picture mode to %s", option)


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
            _LOGGER.warning(
                "Attempted to select unsupported energy saving mode: %s", option
            )
            return

        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            _LOGGER.info("Display is off; ignoring energy saving change %s", option)
            return

        if await self._lg_display.async_set_energy_saving(ENERGY_SAVING_MODES[option]):
            self._current_mode = option
            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to set energy saving mode to %s", option)


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
