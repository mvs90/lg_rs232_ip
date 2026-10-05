"""Picture controls must honour mode locks and confirmed device readback."""

import asyncio
import time
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityPlatformState

from custom_components.lg_rs232_ip.lg_display import LGDisplay
from custom_components.lg_rs232_ip.number import (
    LGDisplayBacklightNumber,
    LGDisplayAspectRatioNumber,
)
from custom_components.lg_rs232_ip.select import LGDisplayAspectRatioSelect
from custom_components.lg_rs232_ip.sensor import LGDisplayEnergySavingSensor


def display_with_modes(energy=0, schedule=0, panel=0, picture=1):
    display = LGDisplay("example.invalid")
    display._last_successful_response = time.monotonic()
    display.async_get_power_status = AsyncMock(return_value=True)
    display.async_get_subcommand = AsyncMock(return_value=panel)
    values = {"jq": energy, "sm": schedule, "dx": picture, "mg": 75}
    display.async_send_command = AsyncMock(
        side_effect=lambda a, b, v, **kw: values.get(a + b) if v == 255 else v
    )
    return display, values


@pytest.mark.parametrize(
    ("energy", "schedule", "panel", "reason"),
    [
        (0, 0, 0, None),
        (1, 0, 0, None),
        (2, 0, 0, None),
        (3, 0, 0, "Maximum energy saving"),
        (4, 0, 0, "Automatic energy saving"),
        (0, 1, 0, "Brightness scheduling is active"),
        (0, 0, 1, "Panel is off (PM/DPM)"),
        (0, 0, 4, "Panel is off (PM/DPM)"),
    ],
)
async def test_backlight_dependency_matrix(energy, schedule, panel, reason):
    display, _ = display_with_modes(energy, schedule, panel)
    entity = LGDisplayBacklightNumber(display, "LG", "test")
    await entity.async_update()
    assert entity.extra_state_attributes["control_status"] == (
        reason or "Manual control available"
    )
    assert entity.available is (reason is None)
    assert entity.native_value == (75 if reason is None else None)
    assert not any(
        call.args[:2] == ("f", "j")
        for call in display.async_send_command.await_args_list
    )
    if reason:
        assert not await display.async_set_backlight(70)
        assert not any(
            call.args[:2] == ("m", "g")
            for call in display.async_send_command.await_args_list
        )


async def test_mode_and_power_changes_clear_stale_backlight_without_changing_modes():
    display, values = display_with_modes()
    entity = LGDisplayBacklightNumber(display, "LG", "test")
    await entity.async_update()
    assert entity.native_value == 75
    values["jq"] = 4
    await entity.async_update()
    assert entity.native_value is None and not entity.available
    values["jq"] = 0
    await entity.async_update()
    assert entity.native_value == 75 and entity.available
    display.async_get_power_status.return_value = False
    await entity.async_update()
    assert entity.native_value is None and not entity.available
    assert entity.extra_state_attributes["control_status"] == "Display is off"
    assert all(
        call.args[2] == 255 for call in display.async_send_command.await_args_list
    )


async def test_picture_mode_does_not_imply_a_lock_and_failed_reads_never_invent_values():
    display, values = display_with_modes(picture=8, schedule=None, panel=None)
    entity = LGDisplayBacklightNumber(display, "LG", "test")
    await entity.async_update()
    assert entity.available and entity.native_value == 75
    values["mg"] = None
    await entity.async_update()
    assert not entity.available and entity.native_value is None
    values["mg"] = 255
    assert await display.async_get_backlight() is None


async def test_backlight_ack_and_readback_must_match():
    display, values = display_with_modes()
    assert not await display.async_set_backlight(70)  # ACK 70, readback still 75.
    assert await display.async_set_backlight(75)
    display.async_send_command.reset_mock()
    for value in (-1, 101, 255, 1.5):
        assert not await display.async_set_backlight(value)
    display.async_send_command.assert_not_awaited()
    values["jq"] = 4
    entity = LGDisplayBacklightNumber(display, "LG", "test")
    entity.async_write_ha_state = Mock()
    with pytest.raises(HomeAssistantError, match="Automatic energy saving"):
        await entity.async_set_native_value(70)
    assert not entity.available


async def test_ng_backoff_is_invalidated_by_modes_but_not_unrelated_writes():
    display = LGDisplay("example.invalid")
    reader = asyncio.StreamReader()
    writer = Mock(drain=AsyncMock())
    display._reader, display._writer, display._connected = reader, writer, True
    energy = 4

    def reply(data):
        nonlocal energy
        if data == b"mg 01 ff\r":
            reader.feed_data(b"g 01 NGffx" if energy == 4 else b"g 01 OK4bx")
        elif data == b"jq 01 00\r":
            energy = 0
            reader.feed_data(b"q 01 OK00x")
        elif data == b"jq 01 ff\r":
            reader.feed_data(b"q 01 OK00x")
        else:
            reader.feed_data(b"f 01 OK32x")

    writer.write.side_effect = reply
    changed = Mock()
    unsubscribe = display.subscribe_picture_settings(changed)
    assert await display.async_get_backlight() is None
    await display.async_set_volume(50)
    assert await display.async_get_backlight() is None
    assert writer.write.call_count == 2
    await display.async_set_energy_saving(0)
    assert await display.async_get_backlight() == 75
    changed.assert_called_once()
    unsubscribe()
    await display.async_set_energy_saving(0)
    changed.assert_called_once()


async def test_external_mode_change_unlocks_optional_read_backoff():
    display, values = display_with_modes()
    await display.async_get_backlight_context()
    key = ("m", "g", 255, "")
    display._unsupported_until[key] = time.monotonic() + 300
    values["dx"] = 5
    await display.async_get_backlight_context()
    assert key not in display._unsupported_until


async def test_aspect_options_raw_compatibility_and_readback():
    display, values = display_with_modes()
    values["kc"] = 6
    select = LGDisplayAspectRatioSelect(display, "LG", "test")
    select.async_write_ha_state = Mock()
    number = LGDisplayAspectRatioNumber(display, "LG", "test")
    assert select.options == ["Full Screen", "Original"]
    await select.async_update()
    assert select.current_option == "Original"
    assert display.aspect_ratio == 6
    assert (number.native_min_value, number.native_max_value, number.native_step) == (
        2,
        6,
        4,
    )
    for bad in (0, 1, 3, 255):
        with pytest.raises(HomeAssistantError):
            await number.async_set_native_value(bad)
        assert not await display.async_set_aspect_ratio(bad)
    with pytest.raises(HomeAssistantError, match="did not confirm"):
        await select.async_select_option("Full Screen")
    assert select.current_option == "Original"
    listener = Mock()
    display.subscribe_aspect_ratio(listener)
    values["kc"] = 2
    await select.async_select_option("Full Screen")
    assert select.current_option == "Full Screen"
    listener.assert_called_once()
    await select.async_update()
    listener.assert_called_once()
    values["kc"] = None
    await select.async_update()
    assert select.current_option is None and not select.available
    display.async_get_power_status.return_value = False
    with pytest.raises(HomeAssistantError, match="must be on"):
        await select.async_select_option("Original")


async def test_auto_energy_sensor_is_known_and_failed_read_is_unknown():
    display, values = display_with_modes(energy=4)
    entity = LGDisplayEnergySavingSensor(display, "LG", "test")
    await entity.async_update()
    assert entity.state == "AUTO"
    values["jq"] = None
    await entity.async_update()
    assert entity.state is None


async def test_backlight_uses_home_assistant_context_without_overwriting_it(tmp_path):
    from homeassistant.core import HomeAssistant

    hass = HomeAssistant(str(tmp_path))
    display, _ = display_with_modes()
    entity = LGDisplayBacklightNumber(display, "LG", "test")
    entity.hass = hass
    entity.entity_id = "number.backlight"
    entity.platform = Mock(platform_name="lg_rs232_ip")
    entity._platform_state = EntityPlatformState.ADDED
    try:
        await entity.async_update()
        entity.async_write_ha_state()
        state = hass.states.get(entity.entity_id)
        assert state.as_dict()["state"] == "75"
        assert state.context.user_id is None
        await entity.async_update()
        entity.async_write_ha_state()
    finally:
        await hass.async_stop(force=True)


async def test_diagnostic_explains_disabled_slider(tmp_path):
    from custom_components.lg_rs232_ip.sensor import LGDisplayBacklightControlSensor
    from homeassistant.core import HomeAssistant

    hass = HomeAssistant(str(tmp_path))
    display, values = display_with_modes(energy=4)
    entity = LGDisplayBacklightControlSensor(display, "test")
    entity.hass = hass
    entity.entity_id = "sensor.backlight_control"
    entity.platform = Mock(platform_name="lg_rs232_ip")
    entity._platform_state = EntityPlatformState.ADDED
    try:
        await entity.async_update()
        entity.async_write_ha_state()
        state = hass.states.get(entity.entity_id)
        assert state.state == "Automatic energy saving"
        assert state.attributes["energy_saving"] == "AUTO"
        assert state.attributes["brightness_scheduling"] is False
        values["jq"] = 0
        values["sm"] = 1
        await entity.async_update()
        entity.async_write_ha_state()
        assert (
            hass.states.get(entity.entity_id).state == "Brightness scheduling is active"
        )
    finally:
        await hass.async_stop(force=True)
