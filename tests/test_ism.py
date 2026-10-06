"""ISM is a documented enumeration, never an arbitrary byte/brightness setting."""

import time
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.lg_rs232_ip.device_profile import ism_methods
from custom_components.lg_rs232_ip.lg_display import LGDisplay
from custom_components.lg_rs232_ip.number import LGDisplayIsmMethodNumber
from custom_components.lg_rs232_ip.select import LGDisplayIsmMethodSelect


@pytest.fixture
def display():
    panel = LGDisplay("example.invalid")
    panel.model_name = "75UH5F-HJ"
    panel._last_successful_response = time.monotonic()
    panel.async_get_power_status = AsyncMock(return_value=True)
    panel.async_send_command = AsyncMock(return_value=8)
    return panel


def test_documented_profiles_and_normal_code():
    assert ism_methods("75UH5F-HJ") == {
        "off": 8,
        "white_wash": 4,
        "user_image": 144,
        "user_video": 145,
    }
    assert ism_methods("86UH5F-H") == ism_methods("75UH5F-HJ")
    assert ism_methods(None)["orbiter"] == 2
    assert ism_methods("55UH5B")["color_wash"] == 32
    assert ism_methods(None)["washing_bar"] == 128


@pytest.mark.parametrize("value", [0, 1, 2, 3, 32, 128, 255, 4.5, True])
async def test_uh5f_rejects_undocumented_and_outdoor_modes_without_io(display, value):
    assert not await display.async_set_ism_method(value)
    display.async_send_command.assert_not_awaited()


async def test_ism_requires_matching_ack_and_fresh_readback(display):
    assert await display.async_set_ism_method(8)
    assert display.async_send_command.await_args.kwargs == {"use_cache": False}
    display.async_send_command.side_effect = [4, 8]
    assert not await display.async_set_ism_method(4)
    display.async_send_command.side_effect = [None]
    assert not await display.async_set_ism_method(4)
    display.async_send_command.reset_mock()
    display.async_get_power_status.return_value = False
    assert not await display.async_set_ism_method(4)
    display.async_send_command.assert_not_awaited()


async def test_named_select_reports_actual_mode_and_failed_read_clears_state(display):
    entity = LGDisplayIsmMethodSelect(display, "LG", "test")
    entity.async_write_ha_state = Mock()
    await entity.async_update()
    assert entity.current_option == "off" and entity.available
    assert entity.extra_state_attributes["protocol_code"] == "0x08"
    assert "Normal picture" in entity.extra_state_attributes["mode_description"]
    assert entity.options == ["off", "white_wash", "user_image", "user_video"]
    await entity.async_select_option("off")
    with pytest.raises(HomeAssistantError, match="Unsupported"):
        await entity.async_select_option("orbiter")
    # An ACK alone cannot switch the visible state to white wash.
    display.async_send_command.side_effect = [4, 8, 8]
    with pytest.raises(HomeAssistantError, match="did not confirm"):
        await entity.async_select_option("white_wash")
    assert entity.current_option == "off"
    display.async_send_command.side_effect = None
    for value in (None, 255, 0):
        display.async_send_command.return_value = value
        await entity.async_update()
        assert entity.current_option is None and not entity.available
    display.async_get_power_status.return_value = False
    with pytest.raises(HomeAssistantError, match="must be on"):
        await entity.async_select_option("off")


async def test_legacy_number_cannot_send_arbitrary_codes_or_silently_ignore_failure(
    display,
):
    entity = LGDisplayIsmMethodNumber(display, "LG", "test")
    entity.async_write_ha_state = Mock()
    for value in (0, 255, 4.1, 2, True):
        with pytest.raises(HomeAssistantError):
            await entity.async_set_native_value(value)
    display.async_send_command.assert_not_awaited()
    await entity.async_set_native_value(8.0)
    assert entity.native_value == 8
    display.async_send_command.return_value = None
    with pytest.raises(HomeAssistantError, match="did not confirm"):
        await entity.async_set_native_value(4)
    assert entity.native_value is None
