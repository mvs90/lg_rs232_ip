"""Validated, shared polling of optional Signage system settings."""

from contextlib import nullcontext
from datetime import timedelta
import asyncio
import logging
import unicodedata

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN
from .web_manager import LGWebError

_LOGGER = logging.getLogger(__name__)
SYSTEM_KEYS = (
    "smartEnergy",
    "signageName",
    "signageSetId",
    "powerOnDelay",
    "noSignalImage",
    "temperatureUnit",
)


def validate_setting(key, value):
    """Return the vendor representation, rejecting unknown keys and control text."""
    if key in {"smartEnergy", "noSignalImage"}:
        if value in ("on", "off"):
            return value
    elif key == "temperatureUnit":
        if value in ("celsius", "fahrenheit"):
            return value
    elif key == "signageName":
        if (
            isinstance(value, str)
            and value.strip()
            and len(value.encode("utf-16-le", errors="replace")) // 2 <= 32
            and not any(unicodedata.category(c).startswith("C") for c in value)
        ):
            return value
    elif key in {"signageSetId", "powerOnDelay"}:
        low, high = (1, 1000) if key == "signageSetId" else (0, 250)
        if not isinstance(value, bool):
            try:
                number = int(value)
                if (
                    str(number) == str(value)
                    or isinstance(value, float)
                    and value == number
                ):
                    if low <= number <= high:
                        return str(number)
            except (TypeError, ValueError, OverflowError):
                pass
    raise ValueError("Invalid or unsupported LG system setting")


def valid_settings(values):
    result = {}
    if not isinstance(values, dict):
        raise LGWebError("Invalid LG system settings response")
    for key in SYSTEM_KEYS:
        try:
            result[key] = validate_setting(key, values.get(key))
        except ValueError:
            pass
    return result


class SystemSettings(DataUpdateCoordinator):
    """One minute polling; confirmed address changes follow the physical device."""

    def __init__(self, hass, entry, display, web, controller, store, remembered=None):
        super().__init__(
            hass,
            _LOGGER,
            name="LG system settings",
            update_interval=timedelta(seconds=60),
            config_entry=entry,
            always_update=False,
        )
        self.entry, self.display, self.web = entry, display, web
        self.controller, self.store = controller, store
        self._settings_lock = asyncio.Lock()
        try:
            self.power_on_delay = int(
                validate_setting(
                    "powerOnDelay", (remembered or {}).get("power_on_delay", 0)
                )
            )
        except (ValueError, AttributeError):
            self.power_on_delay = 0
        self._remembered = remembered

    @staticmethod
    def address_store(hass, entry):
        return Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.address")

    async def _adopt_address(self, values, *, locked=False):
        if "signageSetId" not in values:
            return
        address = int(values["signageSetId"])
        if address == self.display.device_id:
            return
        async with nullcontext() if locked else self.display._command_lock:
            await self.display.async_disconnect()
            self.display.device_id = address
            self.display._unsupported_until.clear()
            self.display._last_power_status = None

    async def _read(self, *, locked=False):
        values = await self.web.async_get_display_settings()
        await self._adopt_address(values, locked=locked)
        if "powerOnDelay" in values:
            self.power_on_delay = int(values["powerOnDelay"])
        remembered = {
            "device_id": self.display.device_id,
            "power_on_delay": self.power_on_delay,
        }
        if remembered != self._remembered:
            # No integration reload, renaming of entities, or writes on every poll.
            await self.store.async_save(remembered)
            self._remembered = remembered
        return values

    async def _async_update_data(self):
        async with self._settings_lock:
            if self.display.is_intentionally_unpowered:
                return {}
            if await self.display.async_get_power_status() is False:
                return {}
            try:
                return await self._read()
            except LGWebError as err:
                raise UpdateFailed("Cannot read LG system settings") from err

    async def async_set(self, key, value):
        try:
            value = validate_setting(key, value)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from None
        async with self._settings_lock, self.controller._control_lock:
            if self.display.is_intentionally_unpowered:
                raise HomeAssistantError("Display must be on to change system settings")
            try:
                before = await self._read()
                if (
                    await self.display.async_get_power_status(use_cache=False)
                    is not True
                ):
                    raise LGWebError("Display must be on to change system settings")
                if key not in before:
                    raise LGWebError("This setting is unavailable on this display")
                values = before
                if before[key] != value:
                    # Keep the RS232 lock until the actual new address is known.
                    # Even cancellation/lost ACK must reconcile a possible write.
                    async with self.display._command_lock:
                        try:
                            await self.web.async_write_display_setting(key, value)
                        except LGWebError:
                            pass
                        finally:
                            for attempt in range(3):
                                values = await self._read(locked=True)
                                if values.get(key) == value:
                                    break
                                if attempt < 2:
                                    await asyncio.sleep(0.2)
                self.async_set_updated_data(values)
                if values.get(key) != value:
                    raise LGWebError("Display did not confirm the requested setting")
                if key == "smartEnergy":
                    self.display._picture_settings_changed()
            except LGWebError as err:
                # A later refresh can recover a changed ID after an ambiguous reply.
                self.async_set_update_error(UpdateFailed(str(err)))
                raise HomeAssistantError(str(err)) from None


class SystemSettingEntity(CoordinatorEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, key, translation_key, icon):
        super().__init__(coordinator)
        self.key = key
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{translation_key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, coordinator.entry.entry_id)}}
        self._attr_icon = icon

    @property
    def available(self):
        return super().available and self.key in (self.coordinator.data or {})
