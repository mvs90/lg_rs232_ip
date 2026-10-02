"""Sensor platform for LG Display RS232/IP integration."""

import logging
from datetime import timedelta
from typing import Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, READ_STATUS
from .lg_display import LGDisplay

_LOGGER = logging.getLogger(__name__)


def _parse_ok_string_response(response: str) -> Optional[str]:
    """Parse generic OK responses that contain string payloads."""
    if not response:
        return None

    response = response.strip()
    ok_index = response.upper().find("OK")
    if ok_index == -1:
        return None

    payload = response[ok_index + 2 :].strip()
    if payload.endswith("x"):
        payload = payload[:-1].strip()

    return payload or None


def _parse_usage_time_response(response: str) -> Optional[int]:
    """Parse the display usage time response into seconds."""
    payload = _parse_ok_string_response(response)
    if not payload:
        return None

    if payload.isdigit():
        return int(payload)

    if not all(c in "0123456789abcdefABCDEF" for c in payload):
        return None

    try:
        raw_bytes = bytes.fromhex(payload)
    except ValueError:
        return None

    ascii_digits = raw_bytes.decode("ascii", errors="ignore")
    if ascii_digits.isdigit():
        return int(ascii_digits)

    raw_value = int.from_bytes(raw_bytes, byteorder="big")

    for scale in (1_000_000, 10_000_000, 1_000_000_000):
        seconds = raw_value / scale
        if 0 < seconds < 315_360_000:
            return int(seconds)

    return raw_value


class LGDisplayBaseSensor(SensorEntity):
    """Base sensor entity with cleaner Home Assistant device-view naming."""

    _attr_entity_registry_enabled_default = False
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC


class LGDisplayAlertSensor(LGDisplayBaseSensor):
    """Sensor that exposes the latest integration alert for notifications."""

    _attr_entity_registry_enabled_default = True

    def __init__(self, alert_state, name: str, unique_id: str) -> None:
        self._alert_state = alert_state
        self._name = name
        self._unique_id = unique_id
        self._alert_unsub = None

    @property
    def unique_id(self) -> str:
        return f"{self._unique_id}_alert_status"

    @property
    def name(self) -> str:
        return "Alert Status"

    @property
    def state(self) -> str:
        return self._alert_state.state

    @property
    def available(self) -> bool:
        return True

    @property
    def icon(self) -> str:
        level = self._alert_state.attributes.get("level", "info")
        if self._alert_state.state == "OK":
            return "mdi:check-circle"
        if level == "error":
            return "mdi:alert-circle"
        return "mdi:alert"

    @property
    def extra_state_attributes(self) -> dict:
        return self._alert_state.attributes

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
            "model": "LG RS232/IP Display",
        }

    async def async_added_to_hass(self) -> None:
        self._alert_unsub = self._alert_state.subscribe(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        if self._alert_unsub is not None:
            self._alert_unsub()
            self._alert_unsub = None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities for LG Display."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    lg_display = data["lg_display"]
    alert_state = data["alert_state"]

    entities = [
        LGDisplayAlertSensor(alert_state, data["name"], config_entry.entry_id),
        LGDisplaySerialNumberSensor(lg_display, data["name"], config_entry.entry_id),
        LGDisplayModelNameSensor(lg_display, data["name"], config_entry.entry_id),
        LGDisplayFirmwareSensor(lg_display, data["name"], config_entry.entry_id),
        LGDisplaySoftwareVersionSensor(lg_display, data["name"], config_entry.entry_id),
        LGDisplayTemperatureSensor(lg_display, data["name"], config_entry.entry_id),
        LGDisplayElapsedTimeSensor(lg_display, data["name"], config_entry.entry_id),
        LGDisplayEnergySavingSensor(lg_display, data["name"], config_entry.entry_id),
        LGDisplayOSDLanguageSensor(lg_display, data["name"], config_entry.entry_id),
        LGDisplayAbnormalStateSensor(lg_display, data["name"], config_entry.entry_id),
        LGDisplayRemoteLockSensor(lg_display, data["name"], config_entry.entry_id),
    ]

    async_add_entities(entities)


class LGDisplaySerialNumberSensor(LGDisplayBaseSensor):
    """Serial number sensor for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        """Initialize the sensor."""
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._state: Optional[str] = None

    @property
    def scan_interval(self) -> timedelta:
        """Return the scan interval."""
        return timedelta(seconds=30)

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._unique_id}_serial_number"

    @property
    def name(self) -> str:
        """Return the name."""
        return "Serial Number"

    @property
    def state(self) -> Optional[str]:
        """Return the state."""
        return self._state

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

    async def async_update(self) -> None:
        """Update the sensor state."""
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        # Use raw command for string responses
        response = await self._lg_display.async_send_raw_command("f", "y", READ_STATUS)
        if response:
            self._state = _parse_ok_string_response(response)


class LGDisplayModelNameSensor(LGDisplayBaseSensor):
    """Model name sensor for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        """Initialize the sensor."""
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._state: Optional[str] = None

    @property
    def scan_interval(self) -> timedelta:
        """Return the scan interval."""
        return timedelta(seconds=30)

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._unique_id}_model_name"

    @property
    def name(self) -> str:
        """Return the name."""
        return "Model Name"

    @property
    def state(self) -> Optional[str]:
        """Return the state."""
        return self._state

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

    async def async_update(self) -> None:
        """Update the sensor state."""
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        # Use raw command for string responses. Some LG panels do not answer
        # `ng` at all, so keep a sensible fallback instead of staying unknown.
        response = await self._lg_display.async_send_raw_command("n", "g", READ_STATUS)
        if response:
            parsed_value = _parse_ok_string_response(response)
            if parsed_value:
                self._state = parsed_value
                return

        if not self._state:
            self._state = self._name


class LGDisplayFirmwareSensor(LGDisplayBaseSensor):
    """Firmware version sensor for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        """Initialize the sensor."""
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._state: Optional[str] = None

    @property
    def scan_interval(self) -> timedelta:
        """Return the scan interval."""
        return timedelta(seconds=30)

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._unique_id}_firmware"

    @property
    def name(self) -> str:
        """Return the name."""
        return "Firmware Version"

    @property
    def state(self) -> Optional[str]:
        """Return the state."""
        return self._state

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

    async def async_update(self) -> None:
        """Update the sensor state."""
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        # Use raw command for string responses
        response = await self._lg_display.async_send_raw_command("f", "w", READ_STATUS)
        if response:
            self._state = _parse_ok_string_response(response)


class LGDisplayEnergySavingSensor(LGDisplayBaseSensor):
    """Energy saving mode sensor for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._state: Optional[str] = None

    @property
    def scan_interval(self) -> timedelta:
        return timedelta(seconds=30)

    @property
    def unique_id(self) -> str:
        return f"{self._unique_id}_energy_saving"

    @property
    def name(self) -> str:
        return "Energy Saving"

    @property
    def state(self) -> Optional[str]:
        return self._state

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

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_send_command("j", "q", READ_STATUS)
        if result is not None:
            self._state = {
                0x00: "OFF",
                0x01: "MINIMUM",
                0x02: "MEDIUM",
                0x03: "MAXIMUM",
            }.get(result, f"UNKNOWN ({result})")


class LGDisplaySoftwareVersionSensor(LGDisplayBaseSensor):
    """Software version sensor for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._state: Optional[str] = None

    @property
    def scan_interval(self) -> timedelta:
        return timedelta(seconds=30)

    @property
    def unique_id(self) -> str:
        return f"{self._unique_id}_software_version"

    @property
    def name(self) -> str:
        return "Software Version"

    @property
    def state(self) -> Optional[str]:
        return self._state

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

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        response = await self._lg_display.async_send_raw_command("f", "z", READ_STATUS)
        if response:
            self._state = _parse_ok_string_response(response)


class LGDisplayOSDLanguageSensor(LGDisplayBaseSensor):
    """OSD language sensor for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._state: Optional[str] = None

    @property
    def scan_interval(self) -> timedelta:
        return timedelta(seconds=30)

    @property
    def unique_id(self) -> str:
        return f"{self._unique_id}_osd_language"

    @property
    def name(self) -> str:
        return "OSD Language"

    @property
    def state(self) -> Optional[str]:
        return self._state

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

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_send_command("f", "i", READ_STATUS)
        if result is not None:
            self._state = {
                0x00: "ENGLISH",
                0x01: "FRENCH",
                0x02: "GERMAN",
                0x03: "SPANISH",
                0x04: "ITALIAN",
                0x05: "PORTUGUESE",
                0x06: "CHINESE",
                0x07: "JAPANESE",
                0x08: "KOREAN",
                0x09: "RUSSIAN",
            }.get(result, f"UNKNOWN ({result})")


class LGDisplayAbnormalStateSensor(LGDisplayBaseSensor):
    """Abnormal state sensor for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._state: Optional[str] = None

    @property
    def scan_interval(self) -> timedelta:
        return timedelta(seconds=30)

    @property
    def unique_id(self) -> str:
        return f"{self._unique_id}_abnormal_state"

    @property
    def name(self) -> str:
        return "Abnormal State"

    @property
    def state(self) -> Optional[str]:
        return self._state

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

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_send_command("k", "z", READ_STATUS)
        if result is not None:
            self._state = {
                0x00: "NORMAL",
                0x01: "ABNORMAL",
            }.get(result, f"UNKNOWN ({result})")


class LGDisplayRemoteLockSensor(LGDisplayBaseSensor):
    """Remote lock sensor for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._state: Optional[str] = None

    @property
    def scan_interval(self) -> timedelta:
        return timedelta(seconds=30)

    @property
    def unique_id(self) -> str:
        return f"{self._unique_id}_remote_lock"

    @property
    def name(self) -> str:
        return "Remote Lock"

    @property
    def state(self) -> Optional[str]:
        return self._state

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

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_send_command("k", "m", READ_STATUS)
        if result is not None:
            self._state = {
                0x00: "UNLOCKED",
                0x01: "LOCKED",
            }.get(result, f"UNKNOWN ({result})")


class LGDisplayTemperatureSensor(LGDisplayBaseSensor):
    """Temperature sensor for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        """Initialize the sensor."""
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._state: Optional[int] = None

    @property
    def scan_interval(self) -> timedelta:
        """Return the scan interval."""
        return timedelta(seconds=30)

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._unique_id}_temperature"

    @property
    def name(self) -> str:
        """Return the name."""
        return "Temperature"

    @property
    def state(self) -> Optional[int]:
        """Return the state."""
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return "°C"

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

    async def async_update(self) -> None:
        """Update the sensor state."""
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_send_command("d", "n", READ_STATUS)
        if result is not None:
            self._state = int(result)


class LGDisplayElapsedTimeSensor(LGDisplayBaseSensor):
    """Elapsed time sensor for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        """Initialize the sensor."""
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._state: Optional[int] = None

    @property
    def scan_interval(self) -> timedelta:
        """Return the scan interval."""
        return timedelta(seconds=30)

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._unique_id}_elapsed_time"

    @property
    def name(self) -> str:
        """Return the name."""
        return "Elapsed Time"

    @property
    def state(self) -> Optional[int]:
        """Return the state."""
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return "hours"

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

    async def async_update(self) -> None:
        """Update the sensor state."""
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_send_command("d", "l", READ_STATUS)
        if result is not None:
            self._state = int(result)
