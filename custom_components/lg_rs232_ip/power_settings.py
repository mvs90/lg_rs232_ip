"""Shared, verified RS232 power configuration, independent of the web/app API."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity, DataUpdateCoordinator, UpdateFailed,
)

from .command_queue import PriorityLock, interactive_command
from .const import DOMAIN, READ_STATUS
from .device_profile import ok_payload

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PowerSetting:
    command: str
    options: dict[str, int]
    parameter: int | None = None


POWER_SETTINGS = {
    # Keep the old suffix so existing automations and entity IDs continue to work.
    "auto_sleep": PowerSetting("fg", {"off": 0, "on": 1}),
    "auto_sleep_no_ir": PowerSetting("mn", {"off": 0, "on": 1}),
    "wake_on_lan": PowerSetting("fw", {"off": 0, "on": 1}),
    "wake_on_wlan": PowerSetting("sn", {"off": 0, "on": 1}, 0x90),
    "pm_mode": PowerSetting("sn", {
        "power_off": 0, "sustain_aspect_ratio": 1, "screen_off": 2,
        "screen_off_always": 3, "screen_off_backlight": 4, "network_ready": 5,
    }, 0x0C),
    "power_on_status": PowerSetting("tr", {
        "last_status": 0, "standby": 1, "power_on": 2,
    }),
    "dpm_wake_up": PowerSetting("sn", {"clock": 0, "clock_and_data": 1}, 0x0B),
}


def remote_power_on_status(values):
    """Report prerequisites, never infer universal wake support from a setting."""
    pm, wol = values.get("pm_mode"), values.get("wake_on_lan")
    if pm is not None and pm != "network_ready":
        return "pm_mode_restricted"
    if wol == "off":
        return "wake_on_lan_disabled"
    if pm == "network_ready" and wol == "on":
        return "network_ready"
    return "unknown"


class PowerSettings(DataUpdateCoordinator):
    def __init__(self, hass, entry, display, controller):
        super().__init__(hass, _LOGGER, name="LG power settings",
                         update_interval=timedelta(seconds=60),
                         config_entry=entry)
        self.entry, self.display, self.controller = entry, display, controller
        self._settings_lock = PriorityLock()
        self.awake = False
        self.issue_id = f"{entry.entry_id}_remote_power_on"

    async def _read(self, key):
        spec = POWER_SETTINGS[key]
        if spec.parameter is None:
            value = await self.display.async_send_command(
                *spec.command, READ_STATUS, use_cache=False)
        else:
            value = await self.display.async_get_subcommand(
                spec.command, spec.parameter, use_cache=False)
        return next((label for label, code in spec.options.items() if code == value), None)

    async def _write(self, key, value):
        spec = POWER_SETTINGS[key]
        code = spec.options[value]
        if spec.parameter is None:
            return await self.display.async_send_command(*spec.command, code) == code
        response = await self.display.async_send_raw_command(
            *spec.command, spec.parameter, query_suffix=f" {code:02x}", use_cache=False)
        return (ok_payload(response) or "").lower() == f"{spec.parameter:02x}{code:02x}"

    def _update_warning(self, values):
        status = remote_power_on_status(values)
        if status in {"pm_mode_restricted", "wake_on_lan_disabled"}:
            ir.async_create_issue(
                self.hass, DOMAIN, self.issue_id, is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="remote_power_on_restricted",
                translation_placeholders={"name": self.entry.title},
            )
        elif status == "network_ready":
            ir.async_delete_issue(self.hass, DOMAIN, self.issue_id)

    async def _async_update_data(self):
        async with self._settings_lock:
            self.awake = False
            if self.display.is_intentionally_unpowered:
                return dict(self.data or {})
            power = await self.display.async_get_power_status()
            if power is None:
                raise UpdateFailed("Cannot read LG power state")
            if not power:
                return dict(self.data or {})
            self.awake = True
            values = {}
            for key in POWER_SETTINGS:
                if (value := await self._read(key)) is not None:
                    values[key] = value
            if not values:
                raise UpdateFailed("No supported LG power settings available")
            self._update_warning(values)
            return values

    async def _read_for_change(self, read):
        """Tolerate a dropped query without waking an off device or replaying writes."""
        for attempt in range(3):
            value = await read()
            if value is not None:
                return value
            if attempt < 2:
                await asyncio.sleep(0.25)
        return None

    @interactive_command
    async def async_set(self, key, value):
        if key not in POWER_SETTINGS or value not in POWER_SETTINGS[key].options:
            raise HomeAssistantError("Invalid LG power setting")
        async with self._settings_lock, self.controller._control_lock:
            if self.display.is_intentionally_unpowered or (
                await self._read_for_change(
                    lambda: self.display.async_get_power_status(use_cache=False)
                ) is not True
            ):
                raise HomeAssistantError("Display must be on to change power settings")
            self.awake = True
            before = await self._read_for_change(lambda: self._read(key))
            if before is None:
                raise HomeAssistantError("This power setting is unavailable on this display")
            actual = before
            if before != value:
                # Do not replay a mutation when an acknowledgement is lost.
                # Read the physical value even after NG, timeout, or a wrong echo.
                await self._write(key, value)
                for attempt in range(3):
                    actual = await self._read(key)
                    if actual == value:
                        break
                    if attempt < 2:
                        await asyncio.sleep(0.25)
            values = dict(self.data or {})
            if actual is None:
                values.pop(key, None)
            else:
                values[key] = actual
            if key == "pm_mode":
                self.display._picture_settings_changed()
            self._update_warning(values)
            self.async_set_updated_data(values)
            if actual != value:
                raise HomeAssistantError("Display did not confirm the requested power setting")


class PowerSettingEntity(CoordinatorEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, key, icon):
        super().__init__(coordinator)
        self.key = key
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, coordinator.entry.entry_id)}}
        self._attr_icon = icon

    @property
    def available(self):
        return (super().available and self.coordinator.awake
                and not self.coordinator.display.is_intentionally_unpowered
                and self.coordinator.display._last_power_status is not False
                and self.key in (self.coordinator.data or {}))
