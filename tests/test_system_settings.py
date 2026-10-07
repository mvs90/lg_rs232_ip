"""Physical system settings, verified writes and safe RS232 address handover."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.lg_rs232_ip.lg_display import LGDisplay
from custom_components.lg_rs232_ip.system_settings import (
    SystemSettings,
    validate_setting,
    valid_settings,
)
from custom_components.lg_rs232_ip.web_manager import LGWebManager, LGWebError
from custom_components.lg_rs232_ip.text import SignageName
from custom_components.lg_rs232_ip.number import SystemSettingsNumber
from custom_components.lg_rs232_ip.switch import SystemSettingsSwitch
from custom_components.lg_rs232_ip.select import SystemTemperatureUnit


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("signageSetId", 0),
        ("signageSetId", 1001),
        ("signageSetId", True),
        ("signageSetId", 2.5),
        ("signageSetId", "02"),
        ("powerOnDelay", 251),
        ("powerOnDelay", float("nan")),
        ("smartEnergy", 1),
        ("noSignalImage", "enabled"),
        ("temperatureUnit", "kelvin"),
        ("signageName", " "),
        ("signageName", "a" * 33),
        ("signageName", "Hi\nthere"),
        ("signageName", "x\x00"),
        ("signageName", "😀" * 17),
        ("signageName", "x\ud800"),
        ("password", "secret"),
    ],
)
def test_reject_invalid_settings(key, value):
    with pytest.raises(ValueError):
        validate_setting(key, value)


def test_bounds_and_partial_capabilities():
    assert validate_setting("signageSetId", 1000.0) == "1000"
    assert validate_setting("powerOnDelay", 250) == "250"
    assert validate_setting("signageName", "Wohnzimmer äöü 😀") == "Wohnzimmer äöü 😀"
    assert valid_settings(
        {
            "smartEnergy": "on",
            "signageSetId": "1",
            "powerOnDelay": "bad",
            "password": "secret",
        }
    ) == {"smartEnergy": "on", "signageSetId": "1"}


@pytest.fixture
async def settings(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    display = LGDisplay("example.invalid")
    display.async_get_power_status = AsyncMock(return_value=True)
    display.async_disconnect = AsyncMock()
    values = {
        "smartEnergy": "on",
        "signageName": "LG SIGNAGE",
        "signageSetId": "1",
        "powerOnDelay": "0",
        "noSignalImage": "on",
        "temperatureUnit": "celsius",
    }
    web = Mock()
    web.async_get_display_settings = AsyncMock(side_effect=lambda: dict(values))

    async def write(key, value):
        values[key] = value

    web.async_write_display_setting = AsyncMock(side_effect=write)
    manager = SystemSettings(
        hass,
        SimpleNamespace(
            entry_id="test", async_on_unload=Mock(), pref_disable_polling=False
        ),
        display,
        web,
        SimpleNamespace(_control_lock=asyncio.Lock()),
        Mock(async_save=AsyncMock()),
    )
    manager.async_set_updated_data(dict(values))
    try:
        yield manager, values
    finally:
        await hass.async_stop(force=True)


async def test_all_entity_types_use_shared_settings_and_keep_ha_names(settings):
    manager, values = settings
    name = SignageName(manager)
    smart = SystemSettingsSwitch(
        manager, "smartEnergy", "smart_energy_saving", "mdi:leaf"
    )
    address = SystemSettingsNumber(
        manager, "signageSetId", "set_id", "mdi:identifier", 1, 1000
    )
    temp = SystemTemperatureUnit(manager)
    await name.async_set_value("Living room")
    await smart.async_turn_off()
    await temp.async_select_option("fahrenheit")
    assert name.native_value == "Living room" and not smart.is_on
    assert temp.current_option == "fahrenheit" and address.native_value == 1
    assert name.unique_id == "test_signage_name" and name.device_info == {
        "identifiers": {("lg_rs232_ip", "test")}
    }
    assert not name.should_poll and not smart.should_poll
    manager.async_set_updated_data({"smartEnergy": "on"})
    assert smart.available and not name.available and name.native_value is None


async def test_id_handover_is_locked_confirmed_persisted_and_supports_large_ids(
    settings,
):
    manager, values = settings

    async def write(key, value):
        assert manager.display._command_lock.locked()
        assert manager.controller._control_lock.locked()
        values[key] = value
        values["powerOnDelay"] = "249"  # Observed firmware side effect of Set ID 1000.

    async def read():
        if values["signageSetId"] == "1000":
            assert manager.display._command_lock.locked()
        return dict(values)

    manager.web.async_write_display_setting.side_effect = write
    manager.web.async_get_display_settings.side_effect = read
    manager.display._unsupported_until = {"old": 500}
    await manager.async_set("signageSetId", 1000)
    assert (
        manager.display.device_id == 1000 and manager.display._unsupported_until == {}
    )
    manager.store.async_save.assert_awaited_with(
        {"device_id": 1000, "power_on_delay": 249}
    )
    assert manager.power_on_delay == 249
    assert manager.data["signageSetId"] == "1000"
    assert not manager.display._command_lock.locked()


async def test_lost_write_ack_is_resolved_by_readback_without_replay(settings):
    manager, values = settings

    async def write(key, value):
        values[key] = value
        raise LGWebError("Lost reply")

    manager.web.async_write_display_setting.side_effect = write
    await manager.async_set("signageSetId", 42)
    assert manager.display.device_id == 42
    manager.web.async_write_display_setting.assert_awaited_once()


async def test_cancelled_id_write_still_reconciles_address(settings):
    manager, values = settings

    async def write(key, value):
        values[key] = value
        raise asyncio.CancelledError

    manager.web.async_write_display_setting.side_effect = write
    with pytest.raises(asyncio.CancelledError):
        await manager.async_set("signageSetId", 2)
    assert manager.display.device_id == 2
    manager.store.async_save.assert_awaited_with({"device_id": 2, "power_on_delay": 0})


async def test_failed_or_unsupported_write_never_claims_success(settings):
    manager, values = settings
    manager.web.async_write_display_setting.side_effect = None
    with pytest.raises(HomeAssistantError, match="did not confirm"):
        await manager.async_set("smartEnergy", "off")
    assert values["smartEnergy"] == "on" and not manager.last_update_success
    manager.web.async_write_display_setting.assert_awaited_once()
    values.pop("smartEnergy")
    manager.web.async_write_display_setting.reset_mock()
    with pytest.raises(HomeAssistantError, match="unavailable"):
        await manager.async_set("smartEnergy", "off")
    manager.web.async_write_display_setting.assert_not_awaited()


async def test_standby_supply_off_and_invalid_requests_do_not_write(settings):
    manager, values = settings
    manager.display.async_get_power_status.return_value = False
    assert await manager._async_update_data() == {}
    manager.web.async_get_display_settings.assert_not_awaited()
    with pytest.raises(HomeAssistantError, match="must be on"):
        await manager.async_set("signageName", "Test")
    manager.web.async_write_display_setting.assert_not_awaited()
    manager.display._power_supply_expected_off = True
    manager.web.async_get_display_settings.reset_mock()
    with pytest.raises(HomeAssistantError):
        await manager.async_set("signageSetId", 3)
    with pytest.raises(HomeAssistantError):
        await manager.async_set("signageSetId", 0)
    manager.web.async_get_display_settings.assert_not_awaited()


async def test_external_id_change_recovers_even_after_tcp_lost(settings):
    manager, values = settings
    values["signageSetId"] = "256"
    manager.display.async_get_power_status.return_value = None
    result = await manager._async_update_data()
    assert result["signageSetId"] == "256" and manager.display.device_id == 256


async def test_one_poll_and_no_redundant_writes_persist_delay_for_wake(settings):
    manager, values = settings
    await manager.async_set("powerOnDelay", 12)
    assert manager.power_on_delay == 12
    manager.store.async_save.assert_awaited_with({"device_id": 1, "power_on_delay": 12})
    manager.web.async_write_display_setting.reset_mock()
    manager.store.async_save.reset_mock()
    await manager.async_set("powerOnDelay", 12)
    await manager._async_update_data()
    manager.web.async_write_display_setting.assert_not_awaited()
    manager.store.async_save.assert_not_awaited()
    manager.web.async_get_display_settings.side_effect = LGWebError("Unavailable")
    with pytest.raises(UpdateFailed):
        await manager._async_update_data()
    assert manager.power_on_delay == 12


async def test_web_allowlist_and_authoritative_id():
    web = LGWebManager("example.invalid", "secret", "ab" * 32)
    web._api = AsyncMock(
        side_effect=[
            {"signageSetId": "1", "smartEnergy": "on", "password": "secret"},
            {"setId": 42},
            "Physical name",
        ]
    )
    values = await web.async_get_display_settings()
    assert values == {
        "smartEnergy": "on",
        "signageSetId": "42",
        "signageName": "Physical name",
    }
    assert "password" not in web._api.await_args_list[0].kwargs["keys"]
    web._api.reset_mock()
    with pytest.raises(LGWebError):
        await web.async_write_display_setting("password", "new")
    web._api.assert_not_awaited()


@pytest.mark.parametrize(
    ("device_id", "wire_id"),
    [(1, "01"), (255, "ff"), (256, "100"), (1000, "3e8"), (1000, "03e8")],
)
async def test_rs232_extended_ids_match_numerically_and_decode_payload(
    device_id, wire_id
):
    from custom_components.lg_rs232_ip.device_profile import ok_payload

    display = LGDisplay("example.invalid", device_id=device_id)
    display._reader = asyncio.StreamReader()
    display._writer = Mock(drain=AsyncMock())
    display._connected = True
    display._writer.write.side_effect = lambda _: display._reader.feed_data(
        f"a 02 OK00xa {wire_id} OK01x".encode()
    )
    assert await display.async_get_power_status(use_cache=False) is True
    display._writer.write.assert_called_once_with(f"ka {device_id:02x} ff\r".encode())
    assert ok_payload(f"v {wire_id} OK3735x") == "3735"


async def test_configured_power_delay_extends_the_wake_deadline(player, monkeypatch):
    from custom_components.lg_rs232_ip import controller

    original = asyncio.timeout
    seen = []

    def timeout(value):
        seen.append(value)
        return original(value)

    monkeypatch.setattr(controller.asyncio, "timeout", timeout)
    player.hass.data["lg_rs232_ip"]["test"]["system_settings"] = SimpleNamespace(
        power_on_delay=250
    )
    assert await player.async_ensure_on()
    assert seen == [310]


async def test_write_set_id_targets_actual_option_not_signage_database():
    web = LGWebManager("example.invalid", "secret", "ab" * 32)
    web._api = AsyncMock(return_value={"returnValue": True})
    await web.async_write_display_setting("signageSetId", 1000)
    web._api.assert_awaited_once_with(
        "setSystemSettings",
        "setSystemSettings",
        category="option",
        settings={"setId": 1000},
        shouldCallback=True,
    )


async def test_missing_set_id_keeps_other_system_settings_usable():
    web = LGWebManager("example.invalid", "secret", "ab" * 32)
    web._api = AsyncMock(
        side_effect=[
            {"smartEnergy": "off"},
            LGWebError("Unsupported"),
            LGWebError("Unsupported"),
        ]
    )
    assert await web.async_get_display_settings() == {"smartEnergy": "off"}


async def test_signage_name_uses_its_public_setter_not_the_shadow_database():
    web = LGWebManager("example.invalid", "secret", "ab" * 32)
    web._api = AsyncMock()
    await web.async_write_display_setting("signageName", "Living room")
    web._api.assert_awaited_once_with("setSignageName", None, signageName="Living room")
