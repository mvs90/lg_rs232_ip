"""Catalog ownership, DST dependencies, partial failures and no setter replay."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.lg_rs232_ip.clock_region import (
    dst_request,
    normalize_dst,
    region_request,
)
from custom_components.lg_rs232_ip.maintenance import MaintenanceSettings
from custom_components.lg_rs232_ip.lg_display import LGDisplay
from custom_components.lg_rs232_ip.web_manager import LGWebError, LGWebManager

RULES = {
    "start_month": 3,
    "start_week": 5,
    "start_weekday": 0,
    "start_hour": 2,
    "end_month": 10,
    "end_week": 5,
    "end_weekday": 0,
    "end_hour": 3,
}


@pytest.mark.parametrize(
    "fields",
    [
        {"start_month": 3},
        {**RULES, "start_week": 6},
        {**RULES, "start_hour": 24},
        {**RULES, "end_weekday": 7},
        {**RULES, "start_month": True},
        {**RULES, "end_hour": 1.5},
    ],
)
def test_rules_validate_whole_set(fields):
    with pytest.raises((ValueError, TypeError)):
        dst_request(True, fields)


def test_dst_normalization_preserves_disabled_identical_factory_rules():
    rules = {
        **RULES,
        "start_month": 1,
        "start_week": 1,
        "start_hour": 0,
        "end_month": 1,
        "end_week": 1,
        "end_hour": 0,
    }
    raw = dst_request(False, rules)
    assert normalize_dst(raw) == raw
    assert normalize_dst({**raw, "dstMode": "on"}) is None
    assert dst_request(False, {}) == {"dstMode": "off"}


@pytest.mark.parametrize(
    "args",
    [
        ("Unknown", "DE", "Europe/Berlin"),
        ("Europe", "Germany", "Europe/Berlin"),
        ("Europe", "DE", "http://host"),
        ("Europe", "DE", ""),
    ],
)
def test_region_validation(args):
    with pytest.raises(ValueError):
        region_request(*args)


@pytest.fixture
async def region(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    display = LGDisplay("example.invalid")
    display.model_name = "75UH5F-HJ"
    display.async_get_power_status = AsyncMock(return_value=True)
    state = {
        "clock_auto": False,
        "timezone": "Europe/Berlin",
        "dst": dst_request(False, RULES),
    }
    cities = [{"ZoneID": "Europe/London", "CountryCode": "GB", "City": "London"}]
    loc = {
        "getlocaleContinent": {"localeContinent": "Europe"},
        "getlocaleCountry": {"localeCountry": "DE"},
        "getTimeZone": {"ZoneID": "Europe/Berlin"},
    }

    async def api(command, event, **params):
        if command == "getCountryList":
            return [{"shortName": "GB"}]
        if command == "getCityList":
            return deepcopy(cities)
        if command in loc:
            return deepcopy(loc[command])
        if command == "getDSTInfo":
            return deepcopy(state["dst"])
        if command == "setCountry":
            loc["getlocaleCountry"]["localeCountry"] = params["country"]
        if command == "setCity":
            loc["getTimeZone"]["ZoneID"] = params["timeZone"]["ZoneID"]
            state["timezone"] = params["timeZone"]["ZoneID"]
        if command == "setDstOnOff":
            state["dst"]["dstMode"] = params["dstOnOff"]
        if command in {"setDstStartTime", "setDstEndTime"}:
            side = "Start" if command == "setDstStartTime" else "End"
            for key, value in params.items():
                state["dst"][
                    "dst" + side + ("DayOfWeek" if key == "Weekday" else key)
                ] = value
        return {"returnValue": True}

    web = Mock(
        _lock=asyncio.Lock(),
        _api=AsyncMock(side_effect=api),
        async_get_maintenance_settings=AsyncMock(side_effect=lambda: deepcopy(state)),
    )
    entry = SimpleNamespace(
        entry_id="test", pref_disable_polling=False, async_on_unload=Mock()
    )
    obj = MaintenanceSettings(
        hass, entry, display, web, SimpleNamespace(_control_lock=asyncio.Lock())
    )
    obj.test_state = state
    yield obj
    await hass.async_stop(force=True)


async def test_timezone_only_uses_device_catalog(region):
    region.test_state["clock_auto"] = True
    with pytest.raises(HomeAssistantError, match="country catalog"):
        await region.async_set_timezone("Europe", "GB", "Europe/Berlin")
    assert not any(c.args[0].startswith("set") for c in region.web._api.await_args_list)
    await region.async_set_timezone("Europe", "GB", "Europe/London")
    city = next(
        c.kwargs["timeZone"]
        for c in region.web._api.await_args_list
        if c.args[0] == "setCity"
    )
    assert city == {"ZoneID": "Europe/London", "CountryCode": "GB", "City": "London"}
    assert region.data["timezone"] == "Europe/London"


async def test_timezone_catalog_and_no_wake(region):
    assert (await region.async_get_timezones("GB"))["timezones"][0][
        "ZoneID"
    ] == "Europe/London"
    region.display.async_get_power_status.return_value = False
    with pytest.raises(HomeAssistantError, match="must be on"):
        await region.async_get_timezones("GB")


async def test_ntp_and_manual_dst_are_mutually_exclusive(region):
    region.test_state["clock_auto"] = True
    with pytest.raises(HomeAssistantError, match="automatic time disabled"):
        await region.async_configure_dst(True, **RULES)
    region.web._api.assert_not_awaited()


async def test_rules_are_disabled_during_update_and_reenabled_after_verification(
    region,
):
    region.test_state["dst"]["dstMode"] = "on"
    await region.async_configure_dst(True, **{**RULES, "start_hour": 1, "end_hour": 2})
    writes = [c for c in region.web._api.await_args_list if c.args[0].startswith("set")]
    assert [c.args[0] for c in writes] == [
        "setDstOnOff",
        "setDstStartTime",
        "setDstEndTime",
        "setDstOnOff",
    ]
    assert (
        writes[0].kwargs["dstOnOff"] == "off" and writes[-1].kwargs["dstOnOff"] == "on"
    )
    assert region.data["dst"]["dstStartHour"] == "1"


async def test_partial_dst_failure_stays_off_and_is_not_replayed(region):
    region.test_state["dst"]["dstMode"] = "on"
    original = region.web._api.side_effect

    async def api(command, event, **kw):
        if command == "setDstEndTime":
            raise LGWebError("lost")
        return await original(command, event, **kw)

    region.web._api.side_effect = api
    with pytest.raises(HomeAssistantError, match="rules"):
        await region.async_configure_dst(
            True, **{**RULES, "start_hour": 1, "end_hour": 2}
        )
    assert region.test_state["dst"]["dstMode"] == "off"
    assert (
        sum(c.args[0] == "setDstEndTime" for c in region.web._api.await_args_list) == 1
    )


async def test_lost_timezone_ack_is_checked_not_replayed(region):
    region.test_state["clock_auto"] = True
    original = region.web._api.side_effect

    async def api(command, event, **kw):
        result = await original(command, event, **kw)
        if command.startswith("set"):
            raise LGWebError("lost")
        return result

    region.web._api.side_effect = api
    await region.async_set_timezone("Europe", "GB", "Europe/London")
    assert sum(c.args[0] == "setCity" for c in region.web._api.await_args_list) == 1


async def test_ntp_activation_clears_manual_dst_first():
    web = LGWebManager("example.invalid", "secret", "00" * 32)
    web._api = AsyncMock(side_effect=[None, {"dstMode": "off"}, {"returnValue": True}])
    await web.async_write_maintenance_settings(
        {"clock_auto": True}, manual_dst={"dstMode": "on"}
    )
    assert [c.args[0] for c in web._api.await_args_list] == [
        "setDstOnOff",
        "getDSTInfo",
        "setNTPStatus",
    ]


async def test_already_automatic_clock_still_requires_dst_off_confirmation(region):
    region.test_state["clock_auto"] = True
    region.test_state["dst"]["dstMode"] = "on"
    region.web.async_write_maintenance_settings = AsyncMock(
        side_effect=LGWebError("not confirmed")
    )
    with pytest.raises(HomeAssistantError, match="did not confirm"):
        await region.async_set("clock_auto", True)
    region.web.async_write_maintenance_settings.assert_awaited_once()
