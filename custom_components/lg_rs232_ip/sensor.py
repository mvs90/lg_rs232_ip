"""Sensor platform for LG Display RS232/IP integration."""

import logging
from datetime import timedelta
from typing import Optional

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, READ_STATUS, OSD_LANGUAGES, ENERGY_SAVING_MODES
from .device_profile import ok_payload, PM_STATES, PM_MODES
from .lg_display import LGDisplay
from .power_settings import PowerSettingEntity, remote_power_on_status
from .system_settings import SystemSettingEntity

_LOGGER = logging.getLogger(__name__)


def _parse_ok_string_response(response: str) -> Optional[str]:
    """Return a complete validated OK payload without guessing its encoding."""
    return ok_payload(response)


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
        LGDisplayBacklightControlSensor(lg_display, config_entry.entry_id),
        LGDisplayOSDLanguageSensor(lg_display, data["name"], config_entry.entry_id),
        LGDisplayRemoteLockSensor(lg_display, data["name"], config_entry.entry_id),
        LGDisplayStatusSensor(
            lg_display,
            data["name"],
            config_entry.entry_id,
            "pm_status",
            "Panel Power Status",
            "sv",
            0x03,
            PM_STATES,
        ),
        LGDisplayStatusSensor(
            lg_display,
            data["name"],
            config_entry.entry_id,
            "pm_mode",
            "Power Management Mode",
            "sn",
            0x0C,
            {v: k for k, v in PM_MODES.items()},
        ),
        LGDisplayStatusSensor(
            lg_display,
            data["name"],
            config_entry.entry_id,
            "signal_status",
            "Input Signal",
            "sv",
            0x02,
            {0: "No signal", 1: "Signal present"},
        ),
    ]

    if manager := data.get("display_app"):
        entities.append(LGDisplayAppSensor(manager, config_entry))
    if power := data.get("power_settings"):
        entities.append(RemotePowerOnSensor(power))
    if maintenance := data.get("maintenance"):
        entities.append(DisplayClockSensor(maintenance))
    async_add_entities(entities)


class DisplayClockSensor(SystemSettingEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator):
        super().__init__(coordinator, "clock", "display_clock", "mdi:clock-outline")

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self.key)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        return {"display_timezone": data.get("timezone"), "automatic": data.get("clock_auto"), "precision": "minute"}


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
        }

    async def async_update(self) -> None:
        """Update the sensor state."""
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        self._state = await self._lg_display.async_get_model_name()


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
        }

    async def async_update(self) -> None:
        """Update the sensor state."""
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        # Use raw command for string responses
        # fw is Wake on LAN, not a firmware query.
        self._state = await self._lg_display.async_get_software_version()


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
        }

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_send_command("j", "q", READ_STATUS)
        if result is not None:
            self._state = next(
                (
                    name
                    for name, value in ENERGY_SAVING_MODES.items()
                    if value == result
                ),
                None,
            )
        else:
            self._state = None


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
        }

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        self._state = await self._lg_display.async_get_software_version()


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
        }

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_send_command("f", "i", READ_STATUS)
        if result is not None:
            self._state = OSD_LANGUAGES.get(result, f"UNKNOWN ({result})")


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
        }

    async def async_update(self) -> None:
        """Update the sensor state."""
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_send_command("d", "l", READ_STATUS)
        if result is not None:
            self._state = int(result)


class LGDisplayStatusSensor(LGDisplayBaseSensor):
    """Opt-in status sensor backed by an echoed LG subcommand."""

    def __init__(
        self, display, name, unique_id, key, label, command, parameter, values
    ):
        self._lg_display = display
        self._attr_unique_id = f"{unique_id}_{key}"
        self._attr_name = label
        self._command = command
        self._parameter = parameter
        self._values = values
        self._attr_native_value = None
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, unique_id)})

    @property
    def available(self):
        return self._lg_display.is_available and self._attr_native_value is not None

    async def async_update(self):
        value = await self._lg_display.async_get_subcommand(
            self._command, self._parameter
        )
        self._attr_native_value = self._values.get(value)


class LGDisplayAppSensor(LGDisplayBaseSensor):
    """Connection and restoration status without paired URLs or sensor contents."""

    _attr_entity_registry_enabled_default = True
    _attr_translation_key = "display_app"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["disabled", "error", "connected", "configured", "ready"]
    _attr_icon = "mdi:monitor-dashboard"

    def __init__(self, manager, entry):
        self.manager = manager
        self._attr_unique_id = f"{entry.entry_id}_display_app"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    @property
    def native_value(self):
        return self.manager.status

    @property
    def extra_state_attributes(self):
        return self.manager.attributes

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.manager.controller.subscribe(self.async_write_ha_state)
        )


class LGDisplayBacklightControlSensor(LGDisplayBaseSensor):
    """Explain a disabled backlight slider without hiding its locking mode."""

    _attr_entity_registry_enabled_default = True
    _attr_name = "Backlight Control"
    _attr_icon = "mdi:brightness-6"

    def __init__(self, display, unique_id):
        self._lg_display = display
        self._attr_unique_id = f"{unique_id}_backlight_control"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, unique_id)})
        self._attr_native_value = None

    @property
    def available(self):
        return self._lg_display.is_available

    async def async_added_to_hass(self):
        self.async_on_remove(
            self._lg_display.subscribe_picture_settings(
                lambda: self.async_schedule_update_ha_state(force_refresh=True)
            )
        )
        await self.async_update()

    async def async_update(self):
        status = await self._lg_display.async_get_backlight_status()
        self._attr_native_value = status["control_status"] or "Manual control available"
        self._attr_extra_state_attributes = {
            "energy_saving": next(
                (
                    name
                    for name, value in ENERGY_SAVING_MODES.items()
                    if value == status["energy_saving"]
                ),
                None,
            ),
            "brightness_scheduling": {0: False, 1: True}.get(
                status["brightness_scheduling"]
            ),
            "panel_state": PM_STATES.get(status["panel_state"]),
            "picture_mode_code": status["picture_mode"],
        }


class RemotePowerOnSensor(PowerSettingEntity, SensorEntity):
    """Last confirmed wake configuration, also visible while the panel is off."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["network_ready", "pm_mode_restricted", "wake_on_lan_disabled", "unknown"]

    def __init__(self, coordinator):
        super().__init__(coordinator, "remote_power_on", "mdi:power-plug-outline")

    @property
    def available(self):
        return self.coordinator.last_update_success and bool(self.coordinator.data)

    @property
    def native_value(self):
        return remote_power_on_status(self.coordinator.data or {})

    @property
    def extra_state_attributes(self):
        values = self.coordinator.data or {}
        return {key: values.get(key) for key in ("pm_mode", "wake_on_lan", "wake_on_wlan")}
