"""Shared clock/ISM configuration, dependencies and verified single writes."""

import asyncio
from datetime import datetime, timedelta, timezone
import ipaddress
import logging
import re

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .system_settings import SystemSettingEntity
from .web_manager import LGWebError

_LOGGER = logging.getLogger(__name__)
DURATIONS = [str(n) for n in (*range(1, 11), 20, 30, 60, 90, 120, 180, 240)]
REPEATS = {"once": "immediately", "repeat": "repeat", "schedule": "scheduling"}
MODES = {"normal", "whiteWash", "userImage", "userVideo"}
DAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
NTP_KEYS = (
    "ntpServerMode",
    "ntpServerType",
    "ntpServerIpv4",
    "ntpServerIpv6",
    "ntpServerUrl",
)
MAINTENANCE_KEYS = (
    *NTP_KEYS,
    "ismMode",
    "ismTimer",
    "ismPeriod",
    "ismTime",
    "ismStartTime",
    "ismEndTime",
    "ismDays",
)


def integer(value, minimum, maximum):
    if isinstance(value, bool):
        raise ValueError("Expected a whole number")
    result = int(value)
    if result != float(value) or not minimum <= result <= maximum:
        raise ValueError("Value outside LG's supported range")
    return result


def ntp_changes(server):
    if not isinstance(server, str) or len(server) > 253:
        raise ValueError("Use an NTP host name or IP address")
    server = server.strip()
    if not server:
        return {"ntpServerMode": "auto"}
    try:
        address = ipaddress.ip_address(server)
    except ValueError:
        if not re.fullmatch(
            r"(?=.{1,253}\Z)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.?",
            server,
        ) or re.fullmatch(r"[0-9.]+", server):
            raise ValueError(
                "Use a host name without URL, port, credentials or path"
            ) from None
        return {
            "ntpServerMode": "manual",
            "ntpServerType": "url",
            "ntpServerUrl": server.lower().rstrip("."),
        }
    if address.is_unspecified or address.is_multicast or "%" in server:
        raise ValueError("Use a unicast NTP server address")
    kind = "ipv4" if address.version == 4 else "ipv6"
    return {
        "ntpServerMode": "manual",
        "ntpServerType": kind,
        "ntpServer" + kind.capitalize(): str(address),
    }


def validate_changes(values):
    if not isinstance(values, dict) or not values:
        raise ValueError("No settings supplied")
    result = {}
    for key, value in values.items():
        if key == "clock_auto" and isinstance(value, bool):
            result[key] = value
        elif (
            key == "clock"
            and isinstance(value, datetime)
            and value.tzinfo is not None
            and 2010 <= value.year <= 2099
        ):
            result[key] = value.replace(second=0, microsecond=0)
        elif key == "ismTimer" and value in REPEATS.values():
            result[key] = value
        elif key == "ismPeriod":
            result[key] = integer(value, 1, 24)
        elif key == "ismTime" and str(value) in DURATIONS:
            result[key] = str(value)
        elif key == "ismDays" and isinstance(value, list) and len(value) <= 7 and all(isinstance(day, str) and day in DAYS for day in value):
            result[key] = [day for day in DAYS if day in value]
        elif key in {"ismStartTime", "ismEndTime"}:
            result[key] = str(integer(value, 0, 1439))
        elif key == "ntpServerMode" and value in {"auto", "manual"}:
            result[key] = value
        elif key == "ntpServerType" and value in {"ipv4", "ipv6", "url"}:
            result[key] = value
        elif key in {"ntpServerIpv4", "ntpServerIpv6", "ntpServerUrl"}:
            changes = ntp_changes(value)
            if key not in changes:
                raise ValueError("NTP address and address type do not match")
            result[key] = changes[key]
        else:
            raise ValueError("Invalid or unsupported LG clock/ISM setting")
    if ("clock_auto" in result or "clock" in result) and len(result) != 1:
        raise ValueError("Set clock parameters separately")
    return result


def normalize_settings(values, clock):
    result = {}
    for key in MAINTENANCE_KEYS:
        value = values.get(key)
        try:
            if key == "ismMode":
                if value in MODES:
                    result[key] = value
            elif key in {"ntpServerIpv4", "ntpServerIpv6", "ntpServerUrl"}:
                # Factory placeholders are valid reads, never valid custom servers.
                if isinstance(value, str) and len(value) <= 253:
                    result[key] = value
            else:
                result.update(validate_changes({key: value}))
        except (ValueError, TypeError, OverflowError):
            pass
    auto = clock.get("clock_auto", {}).get("useNetworkTime")
    if isinstance(auto, bool):
        result["clock_auto"] = auto
    zone = clock.get("timezone", {}).get("ZoneID")
    if isinstance(zone, str) and len(zone) <= 100:
        result["timezone"] = zone
    raw = clock.get("clock", {})
    try:
        offset = re.search(r"GMT([+-])(\d{2})(\d{2})", raw.get("current", ""))
        if offset:
            minutes = integer(offset[2], 0, 14) * 60 + integer(offset[3], 0, 59)
            tz = timezone(timedelta(minutes=minutes * (1 if offset[1] == "+" else -1)))
            result["clock"] = datetime(
                *(
                    integer(raw.get(k), lo, hi)
                    for k, lo, hi in (
                        ("year", 2010, 2099),
                        ("month", 1, 12),
                        ("day", 1, 31),
                        ("hour", 0, 23),
                        ("minute", 0, 59),
                    )
                ),
                tzinfo=tz,
            )
    except (ValueError, TypeError, OverflowError):
        pass
    if result.get("ntpServerMode") == "auto":
        result["ntp_server"] = ""
    elif result.get("ntpServerMode") == "manual":
        key = {
            "ipv4": "ntpServerIpv4",
            "ipv6": "ntpServerIpv6",
            "url": "ntpServerUrl",
        }.get(result.get("ntpServerType"))
        if key in result:
            result["ntp_server"] = result[key]
    return result


def setting_enabled(key, data):
    if key not in data:
        return False
    if key == "clock":
        return data.get("clock_auto") is False
    if key in {"ismPeriod", "ismTime"}:
        return (
            data.get("ismMode") in MODES - {"normal"}
            and data.get("ismTimer") == "repeat"
        )
    if key in {"ismStartTime", "ismEndTime", "ismDays"}:
        return (
            data.get("ismMode") in MODES - {"normal"}
            and data.get("ismTimer") == "scheduling"
        )
    return True


class MaintenanceSettings(DataUpdateCoordinator):
    def __init__(self, hass, entry, display, web, controller):
        super().__init__(
            hass,
            _LOGGER,
            name="LG clock and ISM",
            update_interval=timedelta(seconds=60),
            config_entry=entry,
            always_update=False,
        )
        self.entry, self.display, self.web, self.controller = (
            entry,
            display,
            web,
            controller,
        )
        self._settings_lock = asyncio.Lock()

    async def _read(self):
        return await self.web.async_get_maintenance_settings()

    async def _async_update_data(self):
        async with self._settings_lock:
            if (
                self.display.is_intentionally_unpowered
                or await self.display.async_get_power_status() is not True
            ):
                return {}
            try:
                return await self._read()
            except LGWebError as err:
                raise UpdateFailed("Cannot read LG clock/ISM settings") from err

    async def async_set_day(self, day, enabled):
        if day not in DAYS or not isinstance(enabled, bool):
            raise HomeAssistantError("Invalid ISM weekday")
        await self.async_set("ismDays", [], day_change=(day, enabled))

    async def async_set(self, key, value, *, day_change=None):
        try:
            changes = (
                ntp_changes(value)
                if key == "ntp_server"
                else validate_changes({key: value})
            )
        except (ValueError, TypeError, OverflowError) as err:
            raise HomeAssistantError(str(err)) from None
        async with self._settings_lock, self.controller._control_lock:
            if self.display.is_intentionally_unpowered:
                raise HomeAssistantError(
                    "Display must be on to change clock/ISM settings"
                )
            try:
                for attempt in range(3):
                    power = await self.display.async_get_power_status(use_cache=False)
                    if power is not None:
                        break
                    if attempt < 2:
                        await asyncio.sleep(0.25)
                if power is not True:
                    raise LGWebError("Display must be on to change clock/ISM settings")
                before = await self._read()
                if not setting_enabled(key, before):
                    raise LGWebError(
                        "Setting is unavailable in the current clock/ISM mode"
                    )
                if not all(k in before for k in changes):
                    raise LGWebError("Setting is not supported by this display")
                if day_change is not None:
                    day, enabled = day_change
                    days = set(before["ismDays"])
                    days.add(day) if enabled else days.discard(day)
                    changes = validate_changes({"ismDays": [d for d in DAYS if d in days]})
                if key == "clock":
                    changes[key] = changes[key].astimezone(before[key].tzinfo)
                target = {**before, **changes}
                if key in {"ismStartTime", "ismEndTime"} and target.get(
                    "ismStartTime"
                ) == target.get("ismEndTime"):
                    raise LGWebError("ISM start and end must be different")
                after = before
                if any(before.get(k) != v for k, v in changes.items()):
                    try:
                        await self.web.async_write_maintenance_settings(changes)
                    except LGWebError:
                        pass  # Only fresh readback resolves a lost ACK; never replay.
                    for attempt in range(3):
                        await asyncio.sleep(0.25)
                        after = await self._read()
                        if self._matches(changes, after):
                            break
                self.async_set_updated_data(after)
                if not self._matches(changes, after):
                    raise LGWebError(
                        "Display did not confirm the requested clock/ISM setting"
                    )
            except LGWebError as err:
                self.async_set_update_error(UpdateFailed(str(err)))
                raise HomeAssistantError(str(err)) from None

    @staticmethod
    def _matches(changes, after):
        return all(
            k in after
            and (
                0 <= (after[k] - v).total_seconds() < 120
                if k == "clock"
                else after[k] == v
            )
            for k, v in changes.items()
        )


class MaintenanceEntity(SystemSettingEntity):
    @property
    def available(self):
        return super().available and setting_enabled(
            self.key, self.coordinator.data or {}
        )
