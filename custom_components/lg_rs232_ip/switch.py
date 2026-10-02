"""Switch platform for LG Display RS232/IP integration."""

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, READ_STATUS
from .lg_display import LGDisplay

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)


class LGDisplayBaseSwitch(SwitchEntity):
    """Base switch entity with cleaner Home Assistant device-view naming."""

    _attr_entity_registry_enabled_default = False
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for LG Display."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    lg_display = data["lg_display"]

    entities = [
        LGDisplaySyncAutomationSwitch(hass, data["name"], config_entry.entry_id),
    ]

    entities.extend(
        [
            LGDisplayPowerSwitch(lg_display, data["name"], config_entry.entry_id),
            LGDisplayMuteSwitch(lg_display, data["name"], config_entry.entry_id),
            LGDisplayAutoSleepSwitch(lg_display, data["name"], config_entry.entry_id),
            LGDisplayDpmSwitch(lg_display, data["name"], config_entry.entry_id),
            LGDisplayScreenMuteSwitch(lg_display, data["name"], config_entry.entry_id),
            LGDisplayRemoteLockSwitch(lg_display, data["name"], config_entry.entry_id),
            LGDisplayOsdSelectSwitch(lg_display, data["name"], config_entry.entry_id),
        ]
    )

    async_add_entities(entities)


class LGDisplaySyncAutomationSwitch(LGDisplayBaseSwitch, RestoreEntity):
    """Block or allow linked power automation for LG Display."""

    _attr_entity_registry_enabled_default = True

    _attr_entity_category = None

    def __init__(self, hass: HomeAssistant, name: str, entry_id: str) -> None:
        self.hass = hass
        self._name = name
        self._entry_id = entry_id
        self._is_on = False

    def _update_shared_state(self) -> None:
        if DOMAIN in self.hass.data and self._entry_id in self.hass.data[DOMAIN]:
            self.hass.data[DOMAIN][self._entry_id][
                "sync_automation_enabled"
            ] = not self._is_on

    async def async_added_to_hass(self) -> None:
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._is_on = last_state.state == "on"
        self._update_shared_state()

    @property
    def unique_id(self) -> str:
        return f"{self._entry_id}_sync_automation"

    @property
    def name(self) -> str:
        return "Sync Automation Lock"

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def available(self) -> bool:
        return True

    @property
    def icon(self) -> str:
        return "mdi:lock" if self._is_on else "mdi:lock-open-variant"

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": self._name,
            "manufacturer": "LG",
            "model": "LG RS232/IP Display",
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._is_on = True
        self._update_shared_state()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._is_on = False
        self._update_shared_state()
        self.async_write_ha_state()


class LGDisplayPowerSwitch(LGDisplayBaseSwitch):
    """Power switch for LG Display."""

    _attr_entity_registry_enabled_default = True

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        """Initialize the switch."""
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._is_on = False

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._unique_id}_power"

    @property
    def name(self) -> str:
        """Return the name."""
        return "Power"

    @property
    def is_on(self) -> bool:
        """Return True if switch is on."""
        return self._is_on

    @property
    def available(self) -> bool:
        """Return True unless the display is intentionally unpowered."""
        return True

    @property
    def scan_interval(self) -> int:
        """Return the scan interval in seconds."""
        return 5  # Update every 5 seconds for faster status changes

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:monitor" if self._is_on else "mdi:monitor-off"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this entity."""
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
            "model": "Professional Display",
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the display."""
        player = (
            self.hass.data.get(DOMAIN, {}).get(self._unique_id, {}).get("media_player")
        )
        if player is not None:
            await player.async_turn_on()
            self._is_on = player._state != "off"
            self.async_write_ha_state()
            return
        if await self._lg_display.async_power_on():
            await asyncio.sleep(0.5)  # Wait for display to respond
            status = await self._lg_display.async_get_power_status()
            if status is not None:
                self._is_on = status
            else:
                self._is_on = True  # Assume success if we can't query
            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to turn on LG Display")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the display."""
        player = (
            self.hass.data.get(DOMAIN, {}).get(self._unique_id, {}).get("media_player")
        )
        if player is not None:
            await player.async_turn_off()
            self._is_on = player._state != "off"
            self.async_write_ha_state()
            return
        if await self._lg_display.async_power_off():
            await asyncio.sleep(0.5)  # Wait for display to respond
            status = await self._lg_display.async_get_power_status()
            if status is not None:
                self._is_on = status
            else:
                self._is_on = False  # Assume success if we can't query
            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to turn off LG Display")

    async def async_update(self) -> None:
        """Update the switch state."""
        status = await self._lg_display.async_get_power_status()
        if status is not None:
            self._is_on = status


class LGDisplayMuteSwitch(LGDisplayBaseSwitch):
    """Mute switch for LG Display."""

    _attr_entity_registry_enabled_default = True

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        """Initialize the switch."""
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._is_on = False

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._unique_id}_mute"

    @property
    def name(self) -> str:
        """Return the name."""
        return "Mute"

    @property
    def is_on(self) -> bool:
        """Return True if switch is on."""
        return self._is_on

    @property
    def available(self) -> bool:
        """Return True unless the display is intentionally unpowered."""
        return not self._lg_display.is_intentionally_unpowered

    @property
    def scan_interval(self) -> int:
        """Return the scan interval in seconds."""
        return 5  # Update every 5 seconds for faster status changes

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:volume-off" if self._is_on else "mdi:volume-high"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this entity."""
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
            "model": "Professional Display",
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn mute on."""
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        if await self._lg_display.async_send_command("k", "e", 0x00) is not None:
            self._is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn mute off."""
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        if await self._lg_display.async_send_command("k", "e", 0x01) is not None:
            self._is_on = False
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the switch state."""
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_send_command("k", "e", READ_STATUS)
        if result is not None:
            self._is_on = result == 0x00


class LGDisplayAutoSleepSwitch(LGDisplayBaseSwitch):
    """Auto sleep switch for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._is_on = False

    @property
    def unique_id(self) -> str:
        return f"{self._unique_id}_auto_sleep"

    @property
    def name(self) -> str:
        return "Auto Sleep"

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def available(self) -> bool:
        return not self._lg_display.is_intentionally_unpowered

    @property
    def scan_interval(self) -> int:
        return 30

    @property
    def icon(self) -> str:
        return "mdi:sleep"

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
            "model": "LG RS232/IP Display",
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        if await self._lg_display.async_set_auto_sleep(True):
            self._is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        if await self._lg_display.async_set_auto_sleep(False):
            self._is_on = False
            self.async_write_ha_state()

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_get_auto_sleep()
        if result is not None:
            self._is_on = result


class LGDisplayDpmSwitch(LGDisplayBaseSwitch):
    """DPM switch for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._is_on = False

    @property
    def unique_id(self) -> str:
        return f"{self._unique_id}_dpm"

    @property
    def name(self) -> str:
        return "DPM"

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def available(self) -> bool:
        return not self._lg_display.is_intentionally_unpowered

    @property
    def scan_interval(self) -> int:
        return 30

    @property
    def icon(self) -> str:
        return "mdi:power-plug"

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
            "model": "LG RS232/IP Display",
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        if await self._lg_display.async_set_dpm(True):
            self._is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        if await self._lg_display.async_set_dpm(False):
            self._is_on = False
            self.async_write_ha_state()

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_get_dpm()
        if result is not None:
            self._is_on = result


class LGDisplayScreenMuteSwitch(LGDisplayBaseSwitch):
    """Screen mute switch for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._is_on = False

    @property
    def unique_id(self) -> str:
        return f"{self._unique_id}_screen_mute"

    @property
    def name(self) -> str:
        return "Screen Mute"

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def available(self) -> bool:
        return not self._lg_display.is_intentionally_unpowered

    @property
    def scan_interval(self) -> int:
        return 30

    @property
    def icon(self) -> str:
        return "mdi:monitor-off"

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
            "model": "LG RS232/IP Display",
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        if await self._lg_display.async_set_screen_mute(True):
            self._is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        if await self._lg_display.async_set_screen_mute(False):
            self._is_on = False
            self.async_write_ha_state()

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_get_screen_mute()
        if result is not None:
            self._is_on = result


class LGDisplayRemoteLockSwitch(LGDisplayBaseSwitch):
    """Remote lock switch for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._is_on = False

    @property
    def unique_id(self) -> str:
        return f"{self._unique_id}_remote_lock"

    @property
    def name(self) -> str:
        return "Remote Lock"

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def available(self) -> bool:
        return not self._lg_display.is_intentionally_unpowered

    @property
    def scan_interval(self) -> int:
        return 30

    @property
    def icon(self) -> str:
        return "mdi:lock"

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
            "model": "LG RS232/IP Display",
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        if await self._lg_display.async_set_remote_lock(True):
            self._is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        if await self._lg_display.async_set_remote_lock(False):
            self._is_on = False
            self.async_write_ha_state()

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_get_remote_lock()
        if result is not None:
            self._is_on = result


class LGDisplayOsdSelectSwitch(LGDisplayBaseSwitch):
    """OSD select switch for LG Display."""

    def __init__(self, lg_display: LGDisplay, name: str, unique_id: str) -> None:
        self._lg_display = lg_display
        self._name = name
        self._unique_id = unique_id
        self._is_on = False

    @property
    def unique_id(self) -> str:
        return f"{self._unique_id}_osd_select"

    @property
    def name(self) -> str:
        return "OSD Select"

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def available(self) -> bool:
        return not self._lg_display.is_intentionally_unpowered

    @property
    def scan_interval(self) -> int:
        return 30

    @property
    def icon(self) -> str:
        return "mdi:menu"

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "LG",
            "model": "LG RS232/IP Display",
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        if await self._lg_display.async_set_osd_select(True):
            self._is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        if await self._lg_display.async_set_osd_select(False):
            self._is_on = False
            self.async_write_ha_state()

    async def async_update(self) -> None:
        power_status = await self._lg_display.async_get_power_status()
        if power_status is False:
            return

        result = await self._lg_display.async_get_osd_select()
        if result is not None:
            self._is_on = result
