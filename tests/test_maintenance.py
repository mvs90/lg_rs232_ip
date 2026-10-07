"""Clock offsets, dependency guards, NTP validation and ambiguous writes."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from custom_components.lg_rs232_ip.lg_display import LGDisplay
from custom_components.lg_rs232_ip.maintenance import (
    MaintenanceSettings,
    normalize_settings,
    validate_changes,
    ntp_changes,
    setting_enabled,
)
from custom_components.lg_rs232_ip.web_manager import LGWebManager, LGWebError
from custom_components.lg_rs232_ip.datetime import DisplayDateTime
from custom_components.lg_rs232_ip.time import IsmTime
from custom_components.lg_rs232_ip.select import IsmSettingSelect
from custom_components.lg_rs232_ip.number import IsmStandbyNumber
from custom_components.lg_rs232_ip.switch import ClockAutomaticSwitch
from custom_components.lg_rs232_ip.text import NtpServer
from custom_components.lg_rs232_ip.sensor import DisplayClockSensor


@pytest.mark.parametrize(
    "host",
    [
        "https://pool.ntp.org",
        "user@host",
        "host:123",
        "../host",
        "one two",
        "\x00",
        "-host",
        "a" * 254,
        "0.0.0.0",
        "::",
        "ff02::1",
        "224.1.1.1",
        "256.1.1.1",
        "fe80::1%en0",
    ],
)
def test_bad_ntp_server(host):
    with pytest.raises(ValueError):
        ntp_changes(host)


def test_ntp_types_and_reset():
    assert ntp_changes("") == {"ntpServerMode": "auto"}
    assert ntp_changes("POOL.NTP.ORG.") == {
        "ntpServerMode": "manual",
        "ntpServerType": "url",
        "ntpServerUrl": "pool.ntp.org",
    }
    assert ntp_changes("192.0.2.1")["ntpServerIpv4"] == "192.0.2.1"
    assert ntp_changes("2001:db8::1")["ntpServerIpv6"] == "2001:db8::1"


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"unknown": "x"},
        {"ismTimer": "always"},
        {"ismPeriod": 0},
        {"ismPeriod": 25},
        {"ismPeriod": True},
        {"ismPeriod": 1.5},
        {"ismTime": "11"},
        {"ismStartTime": 1440},
        {"ismEndTime": -1},
        {"clock_auto": 1},
        {"clock": datetime(2026, 1, 1)},
        {"clock_auto": False, "ismTime": "2"},
    ],
)
def test_invalid_configuration(changes):
    with pytest.raises(ValueError):
        validate_changes(changes)


def test_clock_local_components_and_offset_not_ha_timezone():
    values = normalize_settings(
        {"ntpServerMode": "auto", "ismMode": "normal", "ismPeriod": 1},
        {
            "clock_auto": {"useNetworkTime": True},
            "clock": {
                "year": 2026,
                "month": 10,
                "day": 7,
                "hour": 19,
                "minute": 32,
                "current": "Wed Oct 07 2026 19:32:13 GMT+0200 (USR)",
            },
            "timezone": {"ZoneID": "Europe/Berlin"},
        },
    )
    assert values["clock"].astimezone(timezone.utc) == datetime(
        2026, 10, 7, 17, 32, tzinfo=timezone.utc
    )
    assert values["ntp_server"] == "" and values["clock_auto"] is True
    assert normalize_settings({}, {"clock": {"current": "invalid"}}) == {}
    assert normalize_settings({"ismPeriod": "nonsense"}, {}) == {}


@pytest.fixture
async def settings(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    display = LGDisplay("example.invalid")
    display.async_get_power_status = AsyncMock(return_value=True)
    values = {
        "clock_auto": True,
        "clock": datetime(2026, 10, 7, 19, 32, tzinfo=timezone(timedelta(hours=2))),
        "timezone": "Europe/Berlin",
        "ntp_server": "",
        "ntpServerMode": "auto",
        "ntpServerType": "ipv4",
        "ntpServerIpv4": "0.0.0.0",
        "ntpServerIpv6": "::",
        "ntpServerUrl": "",
        "ismMode": "normal",
        "ismTimer": "immediately",
        "ismPeriod": 1,
        "ismTime": "1",
        "ismStartTime": "0",
        "ismEndTime": "1439",
    }
    web = Mock()
    web.async_get_maintenance_settings = AsyncMock(side_effect=lambda: dict(values))

    async def write(changes):
        values.update(changes)

    web.async_write_maintenance_settings = AsyncMock(side_effect=write)
    coordinator = MaintenanceSettings(
        hass,
        SimpleNamespace(
            entry_id="test", async_on_unload=Mock(), pref_disable_polling=False
        ),
        display,
        web,
        SimpleNamespace(_control_lock=asyncio.Lock()),
    )
    coordinator.async_set_updated_data(dict(values))
    try:
        yield coordinator, values
    finally:
        await hass.async_stop(force=True)


async def test_auto_blocks_manual_clock_and_converts_offsets(settings):
    manager, values = settings
    editable = DisplayDateTime(manager)
    sensor = DisplayClockSensor(manager)
    auto = ClockAutomaticSwitch(manager)
    assert not editable.available and sensor.available and auto.is_on
    with pytest.raises(HomeAssistantError, match="unavailable"):
        await editable.async_set_value(datetime(2026, 10, 7, 18, tzinfo=timezone.utc))
    manager.web.async_write_maintenance_settings.assert_not_awaited()
    await auto.async_turn_off()
    assert editable.available
    await editable.async_set_value(
        datetime(2026, 10, 7, 18, 1, 59, tzinfo=timezone.utc)
    )
    assert (
        values["clock"].hour == 20
        and values["clock"].minute == 1
        and values["clock"].second == 0
    )
    assert sensor.extra_state_attributes["display_timezone"] == "Europe/Berlin"
    await auto.async_turn_on()
    assert not editable.available


async def test_ism_dependencies_and_endpoints(settings):
    manager, values = settings
    repeat = IsmSettingSelect(manager, "ismTimer", "ism_repeat")
    duration = IsmSettingSelect(manager, "ismTime", "ism_duration")
    wait = IsmStandbyNumber(manager)
    start = IsmTime(manager, "ismStartTime", "ism_start")
    assert repeat.available and not duration.available and not start.available
    await repeat.async_select_option("repeat")
    assert not duration.available
    values["ismMode"] = "userImage"
    await manager.async_refresh()
    assert duration.available and wait.available and not start.available
    await duration.async_select_option("240")
    await wait.async_set_native_value(24)
    assert values["ismTime"] == "240" and values["ismPeriod"] == 24
    await repeat.async_select_option("schedule")
    assert not duration.available and start.available
    from datetime import time

    await start.async_set_value(time(1, 30))
    assert values["ismStartTime"] == "90"
    with pytest.raises(HomeAssistantError, match="different"):
        await start.async_set_value(time(23, 59))
    with pytest.raises(HomeAssistantError):
        await duration.async_select_option("10")


async def test_lost_ack_readback_success_no_replay_and_refusal(settings):
    manager, values = settings

    async def lost(changes):
        values.update(changes)
        raise LGWebError("lost ACK")

    manager.web.async_write_maintenance_settings.side_effect = lost
    await manager.async_set("clock_auto", False)
    assert manager.web.async_write_maintenance_settings.await_count == 1
    manager.web.async_write_maintenance_settings.side_effect = LGWebError("rejected")
    with pytest.raises(HomeAssistantError, match="did not confirm"):
        await manager.async_set("clock_auto", True)
    assert manager.web.async_write_maintenance_settings.await_count == 2
    assert manager.data["clock_auto"] is False


async def test_power_off_never_changes_settings(settings):
    manager, values = settings
    manager.display.async_get_power_status.return_value = False
    with pytest.raises(HomeAssistantError, match="must be on"):
        await manager.async_set("ntp_server", "pool.ntp.org")
    manager.web.async_write_maintenance_settings.assert_not_awaited()
    await manager.async_refresh()
    assert manager.data == {}


async def test_ntp_server_atomic_and_empty_reset(settings):
    manager, values = settings
    entity = NtpServer(manager)
    await entity.async_set_value("pool.ntp.org")
    manager.web.async_write_maintenance_settings.assert_awaited_once_with(
        ntp_changes("pool.ntp.org")
    )
    assert values["clock_auto"] is True
    await entity.async_set_value("")
    assert values["ntpServerMode"] == "auto"


async def test_web_uses_documented_clock_commands_and_narrow_keys():
    web = LGWebManager("example.invalid", "not-a-real-secret", "ab" * 32)
    web._api = AsyncMock(return_value={})
    await web.async_write_maintenance_settings({"clock_auto": True})
    web._api.assert_awaited_with("setNTPStatus", "ntp", useNTP=True)
    await web.async_write_maintenance_settings(
        {"clock": datetime(2026, 10, 7, 19, 32, tzinfo=timezone(timedelta(hours=2)))}
    )
    web._api.assert_awaited_with(
        "setCurrentTime",
        None,
        utc={"year": "2026", "month": "10", "day": "07", "hour": "19", "minute": "32"},
    )
    await web.async_get_maintenance_settings()
    calls = web._api.await_args_list
    assert any(c.args == ("getCurrentTime", "currentTime") for c in calls)
    assert all("password" not in str(c.kwargs.get("keys", [])) for c in calls)


async def test_days_merge_under_shared_lock(settings):
    from custom_components.lg_rs232_ip.switch import IsmDaySwitch
    manager, values = settings
    values.update(ismMode='userImage', ismTimer='scheduling', ismDays=['TUE'])
    await manager.async_refresh()
    monday, friday = IsmDaySwitch(manager,'MON'), IsmDaySwitch(manager,'FRI')
    assert monday.available and not monday.is_on
    await asyncio.gather(monday.async_turn_on(),friday.async_turn_on())
    assert values['ismDays']==['MON','TUE','FRI']
    await monday.async_turn_off()
    assert values['ismDays']==['TUE','FRI']
    values['ismTimer']='repeat';await manager.async_refresh()
    assert not monday.available
    with pytest.raises(HomeAssistantError):await monday.async_turn_on()


async def test_one_dropped_power_query_recovers_without_replaying_write(settings):
    manager, _=settings
    manager.display.async_get_power_status.side_effect=[None, True]
    await manager.async_set('clock_auto',False)
    assert manager.web.async_write_maintenance_settings.await_count==1
