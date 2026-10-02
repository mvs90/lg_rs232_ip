"""Number platform for LG Display RS232/IP integration."""

import logging
from datetime import timedelta
from typing import Optional

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, READ_STATUS
from .lg_display import LGDisplay

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

    async_add_entities(entities)


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
            "model": "LG RS232/IP Display",
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
            "model": "LG RS232/IP Display",
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
        return self._lg_display.is_available

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
            "model": "LG RS232/IP Display",
        }

    async def async_set_native_value(self, value: float) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        backlight_value = int(value)
        if await self._lg_display.async_set_backlight(backlight_value):
            self._attr_native_value = backlight_value
            self.async_write_ha_state()

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_get_backlight()
        if result is not None:
            self._attr_native_value = int(result)


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
            "model": "LG RS232/IP Display",
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
            "model": "LG RS232/IP Display",
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
            "model": "LG RS232/IP Display",
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
            "model": "LG RS232/IP Display",
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
        self._attr_native_min_value = 0
        self._attr_native_max_value = 255
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
            "model": "LG RS232/IP Display",
        }

    async def async_set_native_value(self, value: float) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        color_temperature_value = int(value)
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
    """ISM method raw value control for LG Display."""

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
        return "ISM Method"

    @property
    def available(self) -> bool:
        return self._lg_display.is_available

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
            "model": "LG RS232/IP Display",
        }

    async def async_set_native_value(self, value: float) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        ism_value = int(value)
        if await self._lg_display.async_set_ism_method(ism_value):
            self._attr_native_value = ism_value
            self.async_write_ha_state()

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_get_ism_method()
        if result is not None:
            self._attr_native_value = int(result)


class LGDisplayAspectRatioNumber(LGDisplayBaseNumber):
    """Aspect ratio raw value control for LG Display."""

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
        return f"{self._unique_id}_aspect_ratio"

    @property
    def name(self) -> str:
        return "Aspect Ratio"

    @property
    def available(self) -> bool:
        return self._lg_display.is_available

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
            "model": "LG RS232/IP Display",
        }

    async def async_set_native_value(self, value: float) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        ratio_value = int(value)
        if await self._lg_display.async_set_aspect_ratio(ratio_value):
            self._attr_native_value = ratio_value
            self.async_write_ha_state()

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_get_aspect_ratio()
        if result is not None:
            self._attr_native_value = int(result)
