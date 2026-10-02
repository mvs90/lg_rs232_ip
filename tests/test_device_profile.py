from unittest.mock import AsyncMock, Mock
import pytest
from custom_components.lg_rs232_ip.device_profile import (
    decode_model,
    decode_software,
    is_uh5f,
)
from custom_components.lg_rs232_ip.lg_display import LGDisplay
from custom_components.lg_rs232_ip.sensor import (
    LGDisplayModelNameSensor,
    LGDisplayFirmwareSensor,
    LGDisplayStatusSensor,
)
from custom_components.lg_rs232_ip.select import (
    LGDisplayDpmDelaySelect,
    LGDisplayPictureModeSelect,
)
from homeassistant.exceptions import HomeAssistantError


@pytest.mark.parametrize(
    ("frame", "model"),
    [
        ("v 01 OK3735554835462d484ax", "75UH5F-HJ"),
        ("v 01 NG00x", None),
        ("v 01 OK123x", None),
        ("v 01 OK3735554835462d484a00x", "75UH5F-HJ"),
        ("v 01 OKff00x", None),
        ("v 01 OK3735", None),
    ],
)
def test_model_ascii(frame, model):
    assert decode_model(frame) == model


def test_version_is_not_wol_or_decimal():
    assert decode_software("z 01 OK041350x") == "04.13.50"
    assert decode_software("w 01 OK01x") is None
    assert decode_software("z 01 NG041350x") is None
    assert is_uh5f("75UH5F-HJ")
    assert not is_uh5f("55UH5C-B")


async def test_identity_sensors_use_documented_commands():
    display = LGDisplay("example.invalid")
    display.async_get_power_status = AsyncMock(return_value=True)
    display.async_send_raw_command = AsyncMock(
        side_effect=["v 01 OK3735554835462d484ax", "z 01 OK041350x"]
    )
    model = LGDisplayModelNameSensor(display, "Friendly name", "test")
    firmware = LGDisplayFirmwareSensor(display, "Friendly name", "test")
    await model.async_update()
    await firmware.async_update()
    assert model.state == "75UH5F-HJ"
    assert firmware.state == "04.13.50"
    assert [
        call.args[:2] for call in display.async_send_raw_command.await_args_list
    ] == [("f", "v"), ("f", "z")]
    await model.async_update()
    assert display.async_send_raw_command.await_count == 2


@pytest.mark.parametrize(
    ("frame", "expected"),
    [
        ("n 01 OK0c05x", 5),
        ("n 01 OK0b05x", None),
        ("n 01 NG0c00x", None),
        ("n 01 OK0cx", None),
    ],
)
async def test_subcommand_requires_echo(frame, expected):
    display = LGDisplay("example.invalid")
    display.async_send_raw_command = AsyncMock(return_value=frame)
    assert await display.async_get_subcommand("sn", 0x0C) == expected


async def test_dpm_read_nonzero_and_write_documented_delay():
    display = LGDisplay("example.invalid")
    display.async_send_command = AsyncMock(return_value=4)
    assert await display.async_get_dpm() is True
    assert await display.async_set_dpm(True)
    display.async_send_command.assert_awaited_with("f", "j", 4)
    select = LGDisplayDpmDelaySelect(display, "Display", "test")
    select.async_write_ha_state = Mock()
    await select.async_update()
    assert select.current_option == "1 minute"
    display.async_send_command.return_value = None
    with pytest.raises(HomeAssistantError):
        await select.async_select_option("3 minutes")
    assert select.current_option == "1 minute"


async def test_uh5f_picture_labels_and_unknown_status():
    display = LGDisplay("example.invalid")
    display.model_name = "75UH5F-HJ"
    display.async_get_power_status = AsyncMock(return_value=True)
    display.async_get_picture_mode = AsyncMock(return_value=1)
    select = LGDisplayPictureModeSelect(display, "Display", "test")
    await select.async_update()
    assert select.current_option == "GENERAL"
    assert "FILMMAKER" not in select.options
    display.async_get_subcommand = AsyncMock(side_effect=[0, None])
    sensor = LGDisplayStatusSensor(
        display,
        "Display",
        "test",
        "signal_status",
        "Signal",
        "sv",
        2,
        {0: "No signal", 1: "Signal present"},
    )
    await sensor.async_update()
    assert sensor.native_value == "No signal"
    await sensor.async_update()
    assert sensor.native_value is None


async def test_unknown_dpm_is_unknown_not_on():
    display = LGDisplay("example.invalid")
    display.async_send_command = AsyncMock(return_value=255)
    assert await display.async_get_dpm() is None
    assert await display.async_set_dpm(True) is False


def test_inventory_handles_fragmented_x_command_and_rejects_writes(monkeypatch):
    from tools.read_display_inventory import read_query

    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    connection.recv.side_effect = [b"x", b" 01 OK", b"01x"]
    monkeypatch.setattr(
        "tools.read_display_inventory.socket.create_connection",
        Mock(return_value=connection),
    )
    assert read_query("example.invalid", 9761, 1, "dx")["response"] == "x 01 OK01x"
    connection.sendall.assert_called_once_with(b"dx 01 ff\r")
    with pytest.raises(ValueError):
        read_query("example.invalid", 9761, 1, "ka 01")
    with pytest.raises(ValueError):
        read_query("example.invalid", 9761, 1, "mc")


async def test_uh5f_color_temperature_rejects_query_sentinel_as_write():
    from custom_components.lg_rs232_ip.number import LGDisplayColorTemperatureNumber

    display = LGDisplay("example.invalid")
    display.model_name = "75UH5F-HJ"
    display.async_get_power_status = AsyncMock(return_value=True)
    display.async_set_color_temperature = AsyncMock()
    number = LGDisplayColorTemperatureNumber(display, "Display", "test")
    assert (number.native_min_value, number.native_max_value) == (0x70, 0xD2)
    with pytest.raises(HomeAssistantError):
        await number.async_set_native_value(0xFF)
    display.async_set_color_temperature.assert_not_awaited()
