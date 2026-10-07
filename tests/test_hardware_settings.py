"""Audio/calibration reject stale, unsupported and unconfirmed changes."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.lg_rs232_ip.hardware_settings import (
    HardwareSettings,
    HARDWARE_SETTINGS,
)
from custom_components.lg_rs232_ip.lg_display import LGDisplay
from custom_components.lg_rs232_ip.number import HardwareNumber
from custom_components.lg_rs232_ip.select import HardwareOptionSelect


@pytest.fixture
async def hardware(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    display = LGDisplay("example.invalid")
    display.async_get_power_status = AsyncMock(return_value=True)
    display.async_send_command = AsyncMock(return_value=0)
    display.async_get_subcommand = AsyncMock(return_value=0)
    entry = SimpleNamespace(
        entry_id="test", pref_disable_polling=False, async_on_unload=Mock()
    )
    result = HardwareSettings(
        hass, entry, display, SimpleNamespace(_control_lock=asyncio.Lock())
    )
    yield result
    await hass.async_stop(force=True)


@pytest.mark.parametrize(
    "key,value",
    [
        ("white_balance_red_gain", 255),
        ("white_balance_red_offset", 128),
        ("white_balance_blue_offset", -1),
        ("audio_balance", True),
        ("audio_balance", 1.1),
        ("audio_out", "external_arc"),
        ("sound_mode", "unknown"),
    ],
)
async def test_invalid_write_cannot_reach_display(hardware, key, value):
    with pytest.raises(HomeAssistantError):
        await hardware.async_set(key, value)
    hardware.display.async_get_power_status.assert_not_awaited()


@pytest.mark.parametrize("power", [False, None])
async def test_no_wake_or_mutation_without_power(hardware, power):
    hardware.display.async_get_power_status.return_value = power
    with pytest.raises(HomeAssistantError, match="must be on"):
        await hardware.async_set("white_balance_red_gain", 192)
    hardware.display.async_send_command.assert_not_awaited()


async def test_lost_ack_resolved_by_fresh_read_not_replay(hardware):
    hardware._read_one = AsyncMock(side_effect=[192, None, 193])
    hardware.display.async_send_command.return_value = None
    await hardware.async_set("white_balance_red_gain", 193)
    hardware.display.async_send_command.assert_awaited_once_with("j", "m", 193)
    assert hardware.data["white_balance_red_gain"] == 193


async def test_rejected_write_reports_actual_value(hardware):
    hardware._read_one = AsyncMock(return_value="STANDARD")
    with pytest.raises(HomeAssistantError, match="did not confirm"):
        await hardware.async_set("sound_mode", "NEWS")
    hardware.display.async_send_command.assert_awaited_once_with("d", "y", 7)
    assert hardware.data["sound_mode"] == "STANDARD"


async def test_unsupported_read_not_zero_and_not_writable(hardware):
    hardware.display.async_send_command.return_value = None
    assert await hardware._read_one("white_balance_green_gain") is None
    with pytest.raises(HomeAssistantError, match="unavailable"):
        await hardware.async_set("white_balance_green_gain", 42)
    assert all(
        c.args[-1] == 255 for c in hardware.display.async_send_command.await_args_list
    )


async def test_new_news_mode_and_existing_identity(hardware):
    hardware.display.async_send_command.return_value = 7
    assert await hardware._read_one("sound_mode") == "NEWS"
    entity = HardwareOptionSelect(hardware, "sound_mode")
    assert entity.unique_id == "test_sound_mode"
    assert entity.options[-1] == "NEWS"
    assert entity.device_info["identifiers"] == {("lg_rs232_ip", "test")}
    for key, spec in HARDWARE_SETTINGS.items():
        if not spec.options:
            assert HardwareNumber(hardware, key).native_max_value == spec.maximum


async def test_poll_keeps_availability_until_result(hardware):
    hardware.awake = True
    hardware.async_set_updated_data({"white_balance_red_gain": 192})
    started, finish = asyncio.Event(), asyncio.Event()

    async def power():
        started.set()
        await finish.wait()
        return True

    hardware.display.async_get_power_status = power
    task = asyncio.create_task(hardware._async_update_data())
    await started.wait()
    assert HardwareNumber(hardware, "white_balance_red_gain").available
    finish.set()
    await task
