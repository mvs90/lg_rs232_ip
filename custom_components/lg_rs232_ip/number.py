"""Number platform for LG Display RS232/IP integration."""

import logging
from datetime import timedelta
from typing import Optional

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, READ_STATUS, ENERGY_SAVING_MODES
from .lg_display import LGDisplay
from .system_settings import SystemSettingEntity
from .maintenance import MaintenanceEntity
from .device_profile import ASPECT_RATIOS, PM_STATES, ism_methods, is_uh5f
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)


class LGDisplayBaseNumber(NumberEntity):
    """Base number entity with cleaner Home Assistant device-view naming."""

    _attr_entity_registry_enabled_default = False
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities for LG Display."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    lg_display = data["lg_display"]

    entities = [
        LGDisplayBrightnessNumber(lg_display, data["name"], config_entry.entry_id),
        LGDisplayVolumeNumber(lg_display, data["name"], config_entry.entry_id),
        LGDisplayBacklightNumber(lg_display, data["name"], config_entry.entry_id),
        LGDisplayContrastNumber(lg_display, data["name"], config_entry.entry_id),
        LGDisplayColorNumber(lg_display, data["name"], config_entry.entry_id),
        LGDisplaySharpnessNumber(lg_display, data["name"], config_entry.entry_id),
        LGDisplayTintNumber(lg_display, data["name"], config_entry.entry_id),
        LGDisplayColorTemperatureNumber(
            lg_display, data["name"], config_entry.entry_id
        ),
        LGDisplayIsmMethodNumber(lg_display, data["name"], config_entry.entry_id),
        LGDisplayAspectRatioNumber(lg_display, data["name"], config_entry.entry_id),
    ]

    if settings := data.get("system_settings"):
        entities.extend([SystemSettingsNumber(settings, "signageSetId", "set_id", "mdi:identifier", 1, 1000),
                         SystemSettingsNumber(settings, "powerOnDelay", "power_on_delay", "mdi:timer-outline", 0, 250)])

    if maintenance := data.get("maintenance"):
        entities.append(IsmStandbyNumber(maintenance))

    async_add_entities(entities)


class IsmStandbyNumber(MaintenanceEntity, NumberEntity):
    _attr_native_min_value = 1
    _attr_native_max_value = 24
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "h"

    def __init__(self, coordinator):
        super().__init__(coordinator, "ismPeriod", "ism_standby", "mdi:timer-sand")

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self.key)

    async def async_set_native_value(self, value):
        await self.coordinator.async_set(self.key, value)


class LGDisplayBrightnessNumber(LGDisplayBaseNumber):
    """Brightness control for LG Display."""

    _attr_entity_registry_enabled_default = True

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        """Initialize the number entity."""
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._attr_native_value: Optional[int] = None
        self._attr_native_min_value = 0
        self._attr_native_max_value = 100
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = "%"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._unique_id}_brightness"

    @property
    def name(self) -> str:
        """Return the name."""
        return "Brightness"

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self._lg_display.is_available

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
        }

    async def async_set_native_value(self, value: float) -> None:
        """Set the brightness value."""
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        brightness_value = int(value)
        if (
            await self._lg_display.async_send_command("k", "h", brightness_value)
            is not None
        ):
            self._attr_native_value = brightness_value
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the number state."""
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_send_command("k", "h", READ_STATUS)
        if result is not None:
            self._attr_native_value = int(result)


class LGDisplayVolumeNumber(LGDisplayBaseNumber):
    """Volume control for LG Display."""

    _attr_entity_registry_enabled_default = True

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        """Initialize the number entity."""
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._attr_native_value: Optional[int] = None
        self._attr_native_min_value = 0
        self._attr_native_max_value = 100
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = "%"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._unique_id}_volume"

    @property
    def name(self) -> str:
        """Return the name."""
        return "Volume"

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self._lg_display.is_available

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
        }

    async def async_set_native_value(self, value: float) -> None:
        """Set the volume value."""
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        volume_value = int(value)
        if (
            await self._lg_display.async_send_command("k", "f", volume_value)
            is not None
        ):
            self._attr_native_value = volume_value
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the number state."""
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_send_command("k", "f", READ_STATUS)
        if result is not None:
            self._attr_native_value = int(result)


class LGDisplayBacklightNumber(LGDisplayBaseNumber):
    """Backlight control for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._attr_native_value: Optional[int] = None
        self._backlight_state = {}
        self._control_status = "Not yet read"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 100
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = "%"

    @property
    def unique_id(self) -> str:
        return f"{self._unique_id}_backlight"

    @property
    def name(self) -> str:
        return "Backlight"

    @property
    def available(self) -> bool:
        return self._lg_display.is_available and self._control_status is None

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
        }

    @property
    def extra_state_attributes(self):
        return {
            "control_status": self._control_status or "Manual control available",
            "energy_saving": next(
                (
                    k
                    for k, v in ENERGY_SAVING_MODES.items()
                    if v == self._backlight_state.get("energy_saving")
                ),
                None,
            ),
            "brightness_scheduling": {0: False, 1: True}.get(
                self._backlight_state.get("brightness_scheduling")
            ),
            "panel_state": PM_STATES.get(self._backlight_state.get("panel_state")),
            "picture_mode_code": self._backlight_state.get("picture_mode"),
        }

    async def async_added_to_hass(self):
        self.async_on_remove(
            self._lg_display.subscribe_picture_settings(
                lambda: self.async_schedule_update_ha_state(force_refresh=True)
            )
        )
        await self.async_update()

    async def async_set_native_value(self, value: float) -> None:
        if not 0 <= value <= 100 or value != int(value):
            raise HomeAssistantError(
                "Backlight must be a whole percentage from 0 to 100"
            )
        if not await self._lg_display.async_set_backlight(int(value)):
            await self.async_update()
            self.async_write_ha_state()
            raise HomeAssistantError(
                "Backlight change not confirmed: "
                + (self._control_status or "display rejected the value")
                + ". Use energy saving Off, Minimum or Medium and disable brightness scheduling for manual control."
            )
        await self.async_update()
        self.async_write_ha_state()

    async def async_update(self) -> None:
        self._backlight_state = await self._lg_display.async_get_backlight_status()
        self._control_status = self._backlight_state["control_status"]
        self._attr_native_value = self._backlight_state["value"]


class LGDisplayContrastNumber(LGDisplayBaseNumber):
    """Contrast control for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._attr_native_value: Optional[int] = None
        self._attr_native_min_value = 0
        self._attr_native_max_value = 100
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = "%"

    @property
    def unique_id(self) -> str:
        return f"{self._unique_id}_contrast"

    @property
    def name(self) -> str:
        return "Contrast"

    @property
    def available(self) -> bool:
        return self._lg_display.is_available

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
        }

    async def async_set_native_value(self, value: float) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        contrast_value = int(value)
        if await self._lg_display.async_set_contrast(contrast_value):
            self._attr_native_value = contrast_value
            self.async_write_ha_state()

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_get_contrast()
        if result is not None:
            self._attr_native_value = int(result)


class LGDisplayColorNumber(LGDisplayBaseNumber):
    """Color control for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._attr_native_value: Optional[int] = None
        self._attr_native_min_value = 0
        self._attr_native_max_value = 100
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = "%"

    @property
    def unique_id(self) -> str:
        return f"{self._unique_id}_color"

    @property
    def name(self) -> str:
        return "Color"

    @property
    def available(self) -> bool:
        return self._lg_display.is_available

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
        }

    async def async_set_native_value(self, value: float) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        color_value = int(value)
        if await self._lg_display.async_set_color(color_value):
            self._attr_native_value = color_value
            self.async_write_ha_state()

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_get_color()
        if result is not None:
            self._attr_native_value = int(result)


class LGDisplaySharpnessNumber(LGDisplayBaseNumber):
    """Sharpness control for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._attr_native_value: Optional[int] = None
        self._attr_native_min_value = 0
        self._attr_native_max_value = 100
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = "%"

    @property
    def unique_id(self) -> str:
        return f"{self._unique_id}_sharpness"

    @property
    def name(self) -> str:
        return "Sharpness"

    @property
    def available(self) -> bool:
        return self._lg_display.is_available

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
        }

    async def async_set_native_value(self, value: float) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        sharpness_value = int(value)
        if await self._lg_display.async_set_sharpness(sharpness_value):
            self._attr_native_value = sharpness_value
            self.async_write_ha_state()

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_get_sharpness()
        if result is not None:
            self._attr_native_value = int(result)


class LGDisplayTintNumber(LGDisplayBaseNumber):
    """Tint control for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._attr_native_value: Optional[int] = None
        self._attr_native_min_value = 0
        self._attr_native_max_value = 100
        self._attr_native_step = 1

    @property
    def unique_id(self) -> str:
        return f"{self._unique_id}_tint"

    @property
    def name(self) -> str:
        return "Tint"

    @property
    def available(self) -> bool:
        return self._lg_display.is_available

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
        }

    async def async_set_native_value(self, value: float) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        tint_value = int(value)
        if await self._lg_display.async_set_tint(tint_value):
            self._attr_native_value = tint_value
            self.async_write_ha_state()

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_get_tint()
        if result is not None:
            self._attr_native_value = int(result)


class LGDisplayColorTemperatureNumber(LGDisplayBaseNumber):
    """Color temperature control for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._attr_native_value: Optional[int] = None
        self._attr_native_min_value = 0x70 if is_uh5f(lg_display.model_name) else 0
        self._attr_native_max_value = 0xD2 if is_uh5f(lg_display.model_name) else 255
        self._attr_native_step = 1

    @property
    def unique_id(self) -> str:
        return f"{self._unique_id}_color_temperature"

    @property
    def name(self) -> str:
        return "Color Temperature"

    @property
    def available(self) -> bool:
        return self._lg_display.is_available

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
        }

    async def async_set_native_value(self, value: float) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        color_temperature_value = int(value)
        if (
            not self.native_min_value
            <= color_temperature_value
            <= self.native_max_value
        ):
            raise HomeAssistantError(
                "Color temperature value is outside this model's range"
            )
        if await self._lg_display.async_set_color_temperature(color_temperature_value):
            self._attr_native_value = color_temperature_value
            self.async_write_ha_state()

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_get_color_temperature()
        if result is not None:
            self._attr_native_value = int(result)


class LGDisplayIsmMethodNumber(LGDisplayBaseNumber):
    """Legacy code control; use the named ISM select for normal operation."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._attr_native_value: Optional[int] = None
        self._attr_native_min_value = 0
        self._attr_native_max_value = 255
        self._attr_native_step = 1

    @property
    def unique_id(self) -> str:
        return f"{self._unique_id}_ism_method"

    @property
    def name(self) -> str:
        return "ISM Method Code"

    @property
    def available(self) -> bool:
        return self._lg_display.is_available and self._attr_native_value is not None

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
        }

    async def async_set_native_value(self, value: float) -> None:
        if (
            isinstance(value, bool)
            or value not in ism_methods(self._lg_display.model_name).values()
        ):
            raise HomeAssistantError("Unsupported ISM code; use the named ISM select")
        if not await self._lg_display.async_set_ism_method(int(value)):
            await self.async_update()
            self.async_write_ha_state()
            raise HomeAssistantError("Display did not confirm ISM method")
        self._attr_native_value = int(value)
        self.async_write_ha_state()

    async def async_update(self) -> None:
        self._attr_native_value = None
        if await self._lg_display.async_get_power_status() is True:
            value = await self._lg_display.async_get_ism_method()
            if value in ism_methods(self._lg_display.model_name).values():
                self._attr_native_value = value


class LGDisplayAspectRatioNumber(LGDisplayBaseNumber):
    """Compatibility control; new installations should use the named select."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._attr_native_value: Optional[int] = None
        self._attr_native_min_value = 2
        self._attr_native_max_value = 6
        self._attr_native_step = 4

    @property
    def unique_id(self) -> str:
        return f"{self._unique_id}_aspect_ratio"

    @property
    def name(self) -> str:
        return "Aspect Ratio Code"

    @property
    def available(self) -> bool:
        return self._lg_display.is_available and self._attr_native_value is not None

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
        }

    async def async_added_to_hass(self):
        self.async_on_remove(
            self._lg_display.subscribe_picture_settings(
                lambda: self.async_schedule_update_ha_state(force_refresh=True)
            )
        )
        await self.async_update()

    async def async_set_native_value(self, value: float) -> None:
        if value not in ASPECT_RATIOS.values():
            raise HomeAssistantError(
                "Aspect ratio supports only 2 (Full Screen) or 6 (Original); use the Aspect Ratio select"
            )
        if await self._lg_display.async_get_power_status() is not True:
            raise HomeAssistantError("Display must be on to change aspect ratio")
        if not await self._lg_display.async_set_aspect_ratio(int(value)):
            await self.async_update()
            self.async_write_ha_state()
            raise HomeAssistantError(
                "Display did not confirm aspect ratio in the current input/mode"
            )
        self._attr_native_value = int(value)
        self.async_write_ha_state()

    async def async_update(self) -> None:
        self._attr_native_value = None
        if await self._lg_display.async_get_power_status() is True:
            self._attr_native_value = await self._lg_display.async_get_aspect_ratio()




class SystemSettingsNumber(SystemSettingEntity, NumberEntity):
    _attr_native_step = 1
    _attr_mode = "box"

    def __init__(self, settings, key, translation_key, icon, low, high):
        super().__init__(settings, key, translation_key, icon)
        self._attr_native_min_value = low
        self._attr_native_max_value = high
        if key == "powerOnDelay":
            self._attr_native_unit_of_measurement = "s"

    @property
    def native_value(self):
        value = (self.coordinator.data or {}).get(self.key)
        return int(value) if value is not None else None

    async def async_set_native_value(self, value):
        await self.coordinator.async_set(self.key, value)
