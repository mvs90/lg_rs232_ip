"""Native power/brightness schedules with fresh slot checks and no blind clears."""

import asyncio
from collections import Counter
from datetime import datetime, timedelta
import json
import logging
import re

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .device_profile import ok_payload, is_uh5f
from .maintenance import integer
from .picture_settings import PictureSettingEntity
from .web_manager import LGWebError

_LOGGER = logging.getLogger(__name__)
DAYS = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")
REPEAT_DAYS = {
    "daily": list(DAYS),
    "weekdays": list(DAYS[1:6]),
    "monday_saturday": list(DAYS[1:]),
    "weekends": ["sun", "sat"],
    **{d: [d] for d in DAYS},
}
REPEAT_CODES = dict(zip(REPEAT_DAYS, range(2, 13), strict=True))
KINDS = {
    "power_on": ("fd", 7, "onTime"),
    "power_off": ("fe", 7, "offTime"),
    "brightness": ("ss", 6, None),
}
SCHEDULE_KEYS = ["onOffTimeSchedule", "easyBrightnessSchedule", "easyBrightnessMode"]


def minute_time(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"(?:[01]\d|2[0-3]):[0-5]\d", value
    ):
        raise ValueError("Use a local display time in HH:MM format")
    return tuple(int(v) for v in value.split(":"))


def schedule_lists(raw):
    """Reject unknown schemas rather than interpreting NG/old shadow fields as empty."""
    result = {}
    for kind, (_, maximum, field) in KINDS.items():
        try:
            rows = (
                json.loads(raw["easyBrightnessSchedule"])
                if kind == "brightness"
                else raw["onOffTimeSchedule"][field]
            )
            if not isinstance(rows, list) or len(rows) > maximum:
                continue
            ids = set()
            for row in rows:
                hour, minute = (
                    integer(row["hour"], 0, 23),
                    integer(row["minute"], 0, 59),
                )
                if kind == "brightness":
                    integer(row["backlight"], 0, 100)
                    identity = f"{hour:02d}:{minute:02d}"
                else:
                    identity = row.get("_id")
                    if not isinstance(identity, str) or not 1 <= len(identity) <= 80:
                        raise ValueError("Invalid schedule identity")
                    days = row["day"]
                    if (
                        not isinstance(days, list)
                        or not days
                        or len(days) != len(set(days))
                        or any(day not in DAYS for day in days)
                    ):
                        raise ValueError("Invalid weekdays")
                    identity = row_identity(kind, row)
                if identity in ids:
                    raise ValueError("Duplicate schedule identity")
                ids.add(identity)
            result[kind] = rows
        except (KeyError, ValueError, TypeError, OverflowError):
            pass
    if raw.get("easyBrightnessMode") in {"on", "off"}:
        result["brightness_enabled"] = raw["easyBrightnessMode"] == "on"
    return result


def row_identity(kind, row):
    clock = f"{int(row['hour']):02d}:{int(row['minute']):02d}"
    return clock if kind == "brightness" else "+".join(sorted(row["day"])) + "@" + clock


def signature(kind, row):
    base = (int(row["hour"]), int(row["minute"]))
    return (
        (*base, int(row["backlight"]))
        if kind == "brightness"
        else (*base, tuple(sorted(row["day"])))
    )


def canonical(row):
    # UH5F regenerates every native _id when any serial schedule changes.
    # Compare all actual settings and supply our own content-based identity.
    result = {k: v for k, v in row.items() if k != "_id"}
    if "day" in result:
        result["day"] = sorted(result["day"])
    return json.dumps(result, sort_keys=True)


def same_rows(a, b):
    return Counter(canonical(r) for r in a) == Counter(canonical(r) for r in b)


class NativeSchedules(DataUpdateCoordinator):
    def __init__(self, hass, entry, display, controller, web):
        super().__init__(
            hass,
            _LOGGER,
            name="LG native schedules",
            update_interval=timedelta(seconds=60),
            config_entry=entry,
            always_update=False,
        )
        self.entry, self.display, self.controller, self.web = (
            entry,
            display,
            controller,
            web,
        )
        self.awake = False
        self._settings_lock = asyncio.Lock()

    async def _read(self):
        if not is_uh5f(await self.display.async_get_model_name()):
            raise LGWebError("Native schedules are verified only for UH5F")
        return schedule_lists(await self.web.async_get_native_schedules())

    async def _async_update_data(self):
        async with self._settings_lock:
            if (
                self.display.is_intentionally_unpowered
                or await self.display.async_get_power_status() is not True
            ):
                self.awake = False
                return {}
            self.awake = True
            if not is_uh5f(await self.display.async_get_model_name()):
                return {}
            try:
                return await self._read()
            except LGWebError as err:
                raise UpdateFailed("Cannot read LG native schedules") from err

    async def _clock_ready(self):
        date = ok_payload(
            await self.display.async_send_raw_command("f", "a", 255, use_cache=False)
        )
        clock = ok_payload(
            await self.display.async_send_raw_command("f", "x", 255, use_cache=False)
        )
        try:
            if (
                not date
                or not clock
                or not re.fullmatch("[0-9a-fA-F]{6}", date)
                or not re.fullmatch("[0-9a-fA-F]{6}", clock)
            ):
                return False
            datetime(
                2010 + int(date[:2], 16),
                int(date[2:4], 16),
                int(date[4:], 16),
                int(clock[:2], 16),
                int(clock[2:4], 16),
                int(clock[4:], 16),
            )
            return True
        except ValueError:
            return False

    async def async_change(
        self, kind, *, time=None, repeat=None, backlight=None, schedule_id=None
    ):
        """Append or remove exactly one item; never rewrite other rows or retry writes."""
        try:
            if kind not in KINDS:
                raise ValueError("Unsupported schedule type")
            remove = schedule_id is not None
            if remove:
                if (
                    not isinstance(schedule_id, str)
                    or not 1 <= len(schedule_id) <= 80
                    or any(v is not None for v in (time, repeat, backlight))
                ):
                    raise ValueError("Remove by schedule ID only")
            else:
                hour, minute = minute_time(time)
                target = {"hour": hour, "minute": minute}
                if kind == "brightness":
                    if repeat is not None:
                        raise ValueError("Brightness schedules repeat daily")
                    target["backlight"] = integer(backlight, 0, 100)
                else:
                    if repeat not in REPEAT_DAYS or backlight is not None:
                        raise ValueError("Unsupported repeat days")
                    target["day"] = REPEAT_DAYS[repeat]
        except (ValueError, TypeError, OverflowError) as err:
            raise HomeAssistantError(str(err)) from None
        async with self._settings_lock, self.controller._control_lock:
            if (
                self.display.is_intentionally_unpowered
                or await self.display.async_get_power_status(use_cache=False)
                is not True
            ):
                raise HomeAssistantError("Display must be on to edit native schedules")
            self.awake = True
            try:
                before = await self._read()
                if kind not in before:
                    raise LGWebError(
                        "The active schedule list could not be read safely"
                    )
                if (
                    kind == "brightness"
                    and before.get("brightness_enabled") is not True
                ):
                    raise LGWebError(
                        "Enable brightness scheduling before editing its entries"
                    )
                if not await self._clock_ready():
                    raise LGWebError(
                        "Set a valid display date and time before editing schedules"
                    )
                rows = before[kind]
                command, maximum, _ = KINDS[kind]
                if remove:
                    matches = [
                        (i, r)
                        for i, r in enumerate(rows)
                        if row_identity(kind, r) == schedule_id
                    ]
                    if len(matches) != 1:
                        raise LGWebError("Schedule no longer exists; refresh the list")
                    index, target = matches[0]
                    # LG's slot order can differ from its native list. Find the
                    # matching serial slot; never equate list position with index.
                    slots = []
                    for slot in range(1, maximum + 1):
                        payload = ok_payload(
                            await self.display.async_send_raw_command(
                                *command,
                                0xF0 + slot,
                                query_suffix=" ff ff",
                                use_cache=False,
                            )
                        )
                        if kind == "brightness":
                            expected = f"{int(target['hour']):02x}{int(target['minute']):02x}{int(target['backlight']):02x}"
                        else:
                            code = next(
                                (
                                    REPEAT_CODES[k]
                                    for k, days in REPEAT_DAYS.items()
                                    if set(days) == set(target["day"])
                                ),
                                None,
                            )
                            if code is None:
                                raise LGWebError(
                                    "This weekday combination needs editing in the LG menu"
                                )
                            expected = f"{0xF0 + slot:02x}{code:02x}{int(target['hour']):02x}{int(target['minute']):02x}"
                        if payload and payload.lower() == expected:
                            slots.append((slot, expected))
                    if len(slots) != 1 or not same_rows(
                        (await self._read()).get(kind, []), rows
                    ):
                        raise LGWebError(
                            "Schedule changed or its serial slot is ambiguous; refresh before removing"
                        )
                    slot, expected = slots[0]
                    # Close the read/lookup window before issuing the delete.
                    current_slot = ok_payload(
                        await self.display.async_send_raw_command(
                            *command,
                            0xF0 + slot,
                            query_suffix=" ff ff",
                            use_cache=False,
                        )
                    )
                    if not current_slot or current_slot.lower() != expected:
                        raise LGWebError(
                            "Serial schedule slot changed before deletion; refresh the list"
                        )
                    value, suffix = 0xE0 + slot, " ff ff"
                    wanted = rows[:index] + rows[index + 1 :]
                else:
                    if any(
                        signature(kind, row) == signature(kind, target) for row in rows
                    ):
                        self.async_set_updated_data(before)
                        return
                    if len(rows) >= maximum:
                        raise LGWebError(
                            f"LG supports at most {maximum} entries for this schedule"
                        )
                    if any(
                        (row["hour"], row["minute"]) == (hour, minute)
                        and (
                            kind == "brightness" or set(row["day"]) & set(target["day"])
                        )
                        for row in rows
                    ):
                        raise LGWebError(
                            "An overlapping entry exists at this time; remove it explicitly first"
                        )
                    value = hour if kind == "brightness" else REPEAT_CODES[repeat]
                    suffix = (
                        f" {minute:02x} {target['backlight']:02x}"
                        if kind == "brightness"
                        else f" {hour:02x} {minute:02x}"
                    )
                    wanted = rows + [target]
                await self.display.async_send_raw_command(
                    *command,
                    value,
                    query_suffix=suffix,
                    use_cache=False,
                    is_query=False,
                )
                verified = False
                after = before
                for attempt in range(3):
                    await asyncio.sleep(0.25)
                    after = await self._read()
                    actual = after.get(kind)
                    if actual is not None:
                        if remove:
                            verified = same_rows(actual, wanted)
                        else:
                            old_rows = Counter(canonical(r) for r in rows)
                            additions = []
                            preserved = []
                            for row in actual:
                                encoded = canonical(row)
                                if old_rows[encoded]:
                                    old_rows[encoded] -= 1
                                    preserved.append(row)
                                else:
                                    additions.append(row)
                            verified = (
                                len(additions) == 1
                                and signature(kind, additions[0])
                                == signature(kind, target)
                                and same_rows(preserved, rows)
                            )
                    if verified:
                        break
                self.async_set_updated_data(after)
                if kind == "brightness":
                    self.display._picture_settings_changed()
                if not verified:
                    raise LGWebError(
                        "LG schedule change was not verified; it may have applied. Refresh before retrying"
                    )
            except LGWebError as err:
                raise HomeAssistantError(str(err)) from None


class NativeScheduleEntity(PictureSettingEntity):
    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)
        self._attr_translation_key = key + "_schedule"
        self._attr_unique_id += "_schedule"
        self._attr_icon = "mdi:calendar-clock"
