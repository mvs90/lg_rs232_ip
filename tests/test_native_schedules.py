"""Schedule safety: actual native lists, matching serial slots and single writes."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.lg_rs232_ip.native_schedules import (
    NativeSchedules,
    schedule_lists,
    minute_time,
)
from custom_components.lg_rs232_ip.lg_display import LGDisplay


@pytest.fixture
async def schedules(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    display = LGDisplay("example.invalid")
    display.model_name = "75UH5F-HJ"
    display.async_get_power_status = AsyncMock(return_value=True)
    display.async_send_raw_command = AsyncMock(return_value=None)
    web = Mock(
        async_get_native_schedules=AsyncMock(
            return_value={
                "onOffTimeSchedule": {"onTime": [], "offTime": []},
                "easyBrightnessSchedule": "[]",
                "easyBrightnessMode": "off",
            }
        )
    )
    entry = SimpleNamespace(
        entry_id="test", pref_disable_polling=False, async_on_unload=Mock()
    )
    result = NativeSchedules(
        hass, entry, display, SimpleNamespace(_control_lock=asyncio.Lock()), web
    )
    result._clock_ready = AsyncMock(return_value=True)
    yield result
    await hass.async_stop(force=True)


def test_shadow_arrays_are_not_active_schedules():
    assert "power_on" not in schedule_lists({"onTimerSchedule": [], "onTimerCount": 0})
    assert schedule_lists({"onOffTimeSchedule": {"onTime": []}}) == {"power_on": []}


@pytest.mark.parametrize(
    "value",
    [
        "broken",
        '[{"hour":24,"minute":0,"backlight":1}]',
        '[{"hour":2,"minute":0,"backlight":101}]',
        '[{"hour":2,"minute":0,"backlight":1},{"hour":2,"minute":0,"backlight":2}]',
        "{}",
    ],
)
def test_corrupt_brightness_list_not_empty(value):
    assert "brightness" not in schedule_lists({"easyBrightnessSchedule": value})


@pytest.mark.parametrize("value", ["24:00", "7:30", "07:60", "07:30:01", None, 17])
def test_bad_times(value):
    with pytest.raises(ValueError):
        minute_time(value)


async def test_empty_native_list_can_add_even_after_ng_slot_reads(schedules):
    before = {"power_on": []}
    row = {
        "hour": 7,
        "minute": 0,
        "day": ["mon", "tue", "wed", "thu", "fri"],
        "_id": "a1",
    }
    schedules._read = AsyncMock(side_effect=[before, {"power_on": [row]}])
    await schedules.async_change("power_on", time="07:00", repeat="weekdays")
    schedules.display.async_send_raw_command.assert_awaited_once_with(
        "f", "d", 3, query_suffix=" 07 00", use_cache=False, is_query=False
    )


async def test_add_preserves_unselected_rows_and_checks_after_lost_ack(schedules):
    old = {"hour": 4, "minute": 0, "day": ["sun"], "_id": "a1"}
    new = {"hour": 7, "minute": 0, "day": ["mon"], "_id": "a2"}
    schedules._read = AsyncMock(
        side_effect=[
            {"power_on": [old]},
            {"power_on": [old]},
            {"power_on": [new, {**old, "_id": "new-internal-id"}]},
        ]
    )
    await schedules.async_change("power_on", time="07:00", repeat="mon")
    assert schedules.display.async_send_raw_command.await_count == 1


async def test_delete_finds_serial_order_and_never_clears_all(schedules):
    a = {"hour": 4, "minute": 37, "day": ["sun"], "_id": "a1"}
    b = {"hour": 5, "minute": 0, "day": ["mon"], "_id": "a2"}
    before = {"power_on": [a, b]}
    schedules._read = AsyncMock(
        side_effect=[before, deepcopy(before), {"power_on": [b]}]
    )

    async def serial(*args, **kw):
        return {0xF1: "d 01 OKf1070500x", 0xF2: "d 01 OKf2060425x"}.get(args[2])

    schedules.display.async_send_raw_command.side_effect = serial
    await schedules.async_change("power_on", schedule_id="sun@04:37")
    writes = [
        c
        for c in schedules.display.async_send_raw_command.await_args_list
        if c.kwargs.get("is_query") is False
    ]
    assert len(writes) == 1 and writes[0].args == ("f", "d", 0xE2)
    assert writes[0].kwargs["query_suffix"] == " ff ff"


async def test_external_edit_aborts_delete_before_mutation(schedules):
    row = {"hour": 4, "minute": 37, "day": ["sun"], "_id": "a1"}
    schedules._read = AsyncMock(side_effect=[{"power_on": [row]}, {"power_on": []}])
    schedules.display.async_send_raw_command.side_effect = lambda *a, **k: (
        "d 01 OKf1060425x" if a[2] == 0xF1 else None
    )
    with pytest.raises(HomeAssistantError, match="changed"):
        await schedules.async_change("power_on", schedule_id="sun@04:37")
    assert not any(
        c.kwargs.get("is_query") is False
        for c in schedules.display.async_send_raw_command.await_args_list
    )


async def test_ambiguous_slot_aborts_delete(schedules):
    row = {"hour": 4, "minute": 37, "day": ["sun"], "_id": "a1"}
    schedules._read = AsyncMock(return_value={"power_on": [row]})
    with pytest.raises(HomeAssistantError, match="ambiguous"):
        await schedules.async_change("power_on", schedule_id="sun@04:37")
    assert not any(
        c.kwargs.get("is_query") is False
        for c in schedules.display.async_send_raw_command.await_args_list
    )


@pytest.mark.parametrize("power", [False, None])
async def test_no_schedule_write_when_power_not_confirmed(schedules, power):
    schedules.display.async_get_power_status.return_value = power
    with pytest.raises(HomeAssistantError, match="must be on"):
        await schedules.async_change("power_on", time="07:00", repeat="daily")
    schedules.display.async_send_raw_command.assert_not_awaited()


async def test_brightness_requires_explicit_mode_enabled(schedules):
    with pytest.raises(HomeAssistantError, match="Enable brightness"):
        await schedules.async_change("brightness", time="07:00", backlight=75)
    schedules.display.async_send_raw_command.assert_not_awaited()


async def test_duplicate_is_noop_overlap_is_error(schedules):
    row = {"hour": 7, "minute": 0, "day": ["sun"], "_id": "a1"}
    schedules._read = AsyncMock(return_value={"power_on": [row]})
    await schedules.async_change("power_on", time="07:00", repeat="sun")
    with pytest.raises(HomeAssistantError, match="overlapping"):
        await schedules.async_change("power_on", time="07:00", repeat="daily")
    schedules.display.async_send_raw_command.assert_not_awaited()


async def test_clock_required_before_writing(schedules):
    schedules._clock_ready.return_value = False
    with pytest.raises(HomeAssistantError, match="valid display date"):
        await schedules.async_change("power_on", time="07:00", repeat="daily")
    schedules.display.async_send_raw_command.assert_not_awaited()


async def test_unconfirmed_add_never_replayed(schedules):
    with pytest.raises(HomeAssistantError, match="may have applied"):
        await schedules.async_change("power_on", time="07:00", repeat="daily")
    assert schedules.display.async_send_raw_command.await_count == 1


async def test_slot_delete_is_not_cached_and_invalidates_empty_slot_rejection():
    display = LGDisplay("example.invalid")
    display.model_name = "75UH5F-HJ"
    display._connected = True
    display._writer = Mock(drain=AsyncMock())
    display._reader = Mock(readuntil=AsyncMock(return_value=b"d 01 OKe1ffffx"))
    key = ("f", "d", 0xE1, " ff ff")
    display._query_cache[key] = (float("inf"), "d 01 OKe1ffffx")
    display._unsupported_until[("f", "d", 0xF1, " ff ff")] = float("inf")
    await display.async_send_raw_command(
        "f", "d", 0xE1, query_suffix=" ff ff", is_query=False
    )
    display._writer.write.assert_called_once_with(b"fd 01 e1 ff ff\r")
    assert not display._unsupported_until and key not in display._query_cache


async def test_initially_off_display_discovers_model_after_wake(schedules):
    schedules.display.model_name = None
    schedules.display.async_get_model_name = AsyncMock(return_value="75UH5F-HJ")
    schedules.display.async_get_power_status.return_value = False
    assert await schedules._async_update_data() == {}
    schedules.display.async_get_model_name.assert_not_awaited()
    schedules.display.async_get_power_status.return_value = True
    assert (await schedules._async_update_data())["power_on"] == []
    assert schedules.display.async_get_model_name.await_count == 2


async def test_other_model_is_unavailable_without_background_errors(schedules):
    schedules.display.model_name = "Other LG"
    assert await schedules._async_update_data() == {}
    schedules.web.async_get_native_schedules.assert_not_awaited()


async def test_slot_reordered_after_native_recheck_is_not_deleted(schedules):
    row = {"hour": 4, "minute": 37, "day": ["sun"], "_id": "a1"}
    schedules._read = AsyncMock(return_value={"power_on": [row]})
    calls = 0

    async def serial(*args, **kwargs):
        nonlocal calls
        if args[2] != 0xF1:
            return None
        calls += 1
        return "d 01 OKf1060425x" if calls == 1 else "d 01 OKf1070538x"

    schedules.display.async_send_raw_command.side_effect = serial
    with pytest.raises(HomeAssistantError, match="slot changed"):
        await schedules.async_change("power_on", schedule_id="sun@04:37")
    assert not any(
        c.kwargs.get("is_query") is False
        for c in schedules.display.async_send_raw_command.await_args_list
    )


@pytest.mark.parametrize(
    "kind, maximum", [("power_on", 7), ("power_off", 7), ("brightness", 6)]
)
async def test_full_list_does_not_overwrite_existing_entries(schedules, kind, maximum):
    rows = [
        {
            "hour": 7,
            "minute": n,
            **(
                {"backlight": 75}
                if kind == "brightness"
                else {"day": ["sun"], "_id": f"a{n}"}
            ),
        }
        for n in range(maximum)
    ]
    schedules._read = AsyncMock(return_value={kind: rows, "brightness_enabled": True})
    kwargs = {"backlight": 75} if kind == "brightness" else {"repeat": "daily"}
    with pytest.raises(HomeAssistantError, match="at most"):
        await schedules.async_change(kind, time="08:00", **kwargs)
    schedules.display.async_send_raw_command.assert_not_awaited()
