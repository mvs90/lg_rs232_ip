"""Picture actions and options must preserve mode/input intent and reject guesses."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.lg_rs232_ip.lg_display import LGDisplay
from custom_components.lg_rs232_ip.picture_settings import (
    PictureSettings, PICTURE_OPTIONS, NATIVE_OPTIONS, native_options,
)
from custom_components.lg_rs232_ip.number import (
    LGDisplayColorTemperatureNumber, LGDisplaySharpnessNumber,
)
from custom_components.lg_rs232_ip.web_manager import LGWebManager, LGWebError


@pytest.fixture
async def picture(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    display = LGDisplay("example.invalid")
    display.model_name = "75UH5F-HJ"
    display.async_get_power_status = AsyncMock(return_value=True)
    display.async_get_picture_mode = AsyncMock(return_value=1)
    display.async_send_command = AsyncMock(return_value=0)
    display.async_get_subcommand = AsyncMock(return_value=0)
    display.async_send_raw_command = AsyncMock(return_value="n 01 OKaf9000x")
    web = Mock()
    web.async_get_picture_options = AsyncMock(return_value={
        "pictureMode": "normal", "pictureModeSettingsActive": "true",
        "pictureControlLimitation": "false", "dynamicContrast": "off",
    })
    web.async_write_picture_option = AsyncMock()
    entry = SimpleNamespace(entry_id="test", pref_disable_polling=False, async_on_unload=Mock())
    controller = SimpleNamespace(_control_lock=asyncio.Lock())
    coordinator = PictureSettings(hass, entry, display, controller, web)
    yield coordinator
    await hass.async_stop(force=True)


@pytest.mark.parametrize(("key", "value", "args", "kwargs"), [
    ("gamma", "high2", ("s", "n", 0xAD), {"query_suffix": " 03", "use_cache": False}),
    ("black_level", "high", ("s", "n", 0xAE), {"query_suffix": " 01", "use_cache": False}),
    ("hdmi_it_content", "on", ("s", "n", 0x99), {"query_suffix": " 01", "use_cache": False}),
    ("deep_color_hdmi1", "on", ("s", "n", 0xAF), {"query_suffix": " 90 01", "use_cache": False}),
    ("deep_color_hdmi2", "off", ("s", "n", 0xAF), {"query_suffix": " 91 00", "use_cache": False}),
    ("deep_color_hdmi3", "on", ("s", "n", 0xAF), {"query_suffix": " 92 01", "use_cache": False}),
])
async def test_exact_picture_frames(picture, key, value, args, kwargs):
    await picture._write_one(key, value)
    picture.display.async_send_raw_command.assert_awaited_once_with(*args, **kwargs)


@pytest.mark.parametrize("response", ["n 01 OKaf9101x", "n 01 OKaf9002x", "n 01 NGaf9000x", "n 01 OKaf900001x", None])
async def test_deep_color_rejects_wrong_input_or_value(picture, response):
    picture.display.async_send_raw_command.return_value = response
    assert await picture._read_one("deep_color_hdmi1") is None


async def test_deep_color_query_and_readback(picture):
    picture.display.async_send_raw_command.return_value = "n 01 OKaf9001x"
    assert await picture._read_one("deep_color_hdmi1") == "on"
    picture.display.async_send_raw_command.assert_awaited_once_with("s", "n", 0xAF, query_suffix=" 90 ff", use_cache=False)


async def test_verified_write_never_replays_lost_ack(picture):
    picture._read_one = AsyncMock(side_effect=["low", None, "high"])
    picture._write_one = AsyncMock(return_value=False)
    await picture.async_set("black_level", "high")
    picture._write_one.assert_awaited_once_with("black_level", "high")
    assert picture.data["black_level"] == "high"


@pytest.mark.parametrize("power", [False, None])
async def test_no_writes_without_confirmed_power(picture, power):
    picture.display.async_get_power_status.return_value = power
    picture._write_one = AsyncMock()
    with pytest.raises(HomeAssistantError, match="must be on"):
        await picture.async_set("gamma", "medium")
    picture._write_one.assert_not_awaited()


async def test_native_write_uses_active_profile_and_fresh_readback(picture):
    before = await picture.web.async_get_picture_options()
    picture.web.async_get_picture_options.side_effect = [before, {**before, "dynamicContrast": "high"}]
    await picture.async_set("dynamic_contrast", "high")
    picture.web.async_write_picture_option.assert_awaited_once_with("dynamic_contrast", "high", "normal")
    assert picture.data["dynamic_contrast"] == "high"


@pytest.mark.parametrize("change", [{"pictureModeSettingsActive": "false"}, {"pictureControlLimitation": "true"}, {"pictureMode": "hdrVivid"}, {"dynamicContrast": "unknown"}])
async def test_native_dependencies_reject_dormant_values(picture, change):
    values = await picture.web.async_get_picture_options()
    picture.web.async_get_picture_options.return_value = {**values, **change}
    with pytest.raises(HomeAssistantError, match="unavailable"):
        await picture.async_set("dynamic_contrast", "high")
    picture.web.async_write_picture_option.assert_not_awaited()


async def test_web_failure_preserves_independent_serial_values(picture):
    picture.web.async_get_picture_options.side_effect = LGWebError("offline")
    values = await picture._async_update_data()
    assert values["gamma"] == "low"
    assert "dynamic_contrast" not in values


async def test_refresh_does_not_temporarily_disable_available_controls(picture):
    picture.awake = True
    started, finish = asyncio.Event(), asyncio.Event()
    async def power_read():
        started.set()
        await finish.wait()
        return True
    picture.display.async_get_power_status = power_read
    task = asyncio.create_task(picture._async_update_data())
    await started.wait()
    assert picture.awake
    finish.set()
    await task


@pytest.mark.parametrize("key", [*PICTURE_OPTIONS, *NATIVE_OPTIONS, "skin_color", "unknown"])
async def test_unknown_options_are_never_sent(picture, key):
    with pytest.raises(HomeAssistantError):
        await picture.async_set(key, "unsupported")
    picture.display.async_send_raw_command.assert_not_awaited()
    picture.web.async_write_picture_option.assert_not_awaited()


@pytest.mark.parametrize(("action", "response", "expected", "args", "suffix"), [
    ("picture_reset", "k 01 OK00x", True, ("f", "k", 0), ""),
    ("picture_reset", "k 01 OK02x", False, ("f", "k", 0), ""),
    ("picture_apply_all_inputs", "n 01 OK5201x", True, ("s", "n", 0x52), " 01"),
    ("picture_apply_all_inputs", "n 01 OK5200x", False, ("s", "n", 0x52), " 01"),
])
async def test_actions_only_use_picture_reset_not_factory_reset(action, response, expected, args, suffix):
    display = LGDisplay("example.invalid")
    display.async_send_raw_command = AsyncMock(return_value=response)
    assert await display.async_picture_action(action) is expected
    kwargs = {"use_cache": False, **({"query_suffix": suffix} if suffix else {})}
    display.async_send_raw_command.assert_awaited_once_with(*args, **kwargs)
    display.async_send_raw_command.reset_mock()
    assert not await display.async_picture_action("factory_reset")
    display.async_send_raw_command.assert_not_awaited()


async def test_action_lost_ack_reports_uncertainty_without_retry(picture):
    picture.display.async_picture_action = AsyncMock(return_value=False)
    with pytest.raises(HomeAssistantError, match="may have applied"):
        await picture.async_action("picture_reset")
    picture.display.async_picture_action.assert_awaited_once()


@pytest.mark.parametrize("mode", [None, 0xFF])
async def test_actions_require_a_known_current_preset(picture, mode):
    picture.display.async_get_picture_mode.return_value = mode
    picture.display.async_picture_action = AsyncMock()
    with pytest.raises(HomeAssistantError, match="mode is unknown"):
        await picture.async_action("picture_reset")
    picture.display.async_picture_action.assert_not_awaited()


@pytest.mark.parametrize(("value", "code"), [(3200, 0x70), (6500, 0x91), (10000, 0xB4), (13000, 0xD2)])
async def test_kelvin_roundtrip(picture, value, code):
    display = picture.display
    display.async_read_picture_number = AsyncMock(return_value=code)
    display.async_write_picture_number = AsyncMock(return_value=True)
    number = LGDisplayColorTemperatureNumber(display, "LG", "test", picture)
    number.async_write_ha_state = Mock()
    await number.async_set_native_value(value)
    assert number.native_value == value and number.native_unit_of_measurement == "K"
    display.async_write_picture_number.assert_awaited_once_with("color_temperature", code)


@pytest.mark.parametrize("value", [51, 255, 1.5, -1, True])
async def test_sharpness_correct_range(picture, value):
    number = LGDisplaySharpnessNumber(picture.display, "LG", "test")
    assert number.native_max_value == 50
    with pytest.raises(HomeAssistantError):
        await number.async_set_native_value(value)
    picture.display.async_send_command.assert_not_awaited()


async def test_slider_failed_read_clears_old_value(picture):
    display = picture.display
    display.async_read_picture_number = AsyncMock(side_effect=[25, None])
    number = LGDisplaySharpnessNumber(display, "LG", "test")
    await number.async_update()
    assert number.native_value == 25
    await number.async_update()
    assert number.native_value is None


async def test_native_api_does_not_offer_arbitrary_database_writes():
    web = LGWebManager("example.invalid", "unused", "ab" * 32)
    web._api = AsyncMock()
    await web.async_write_picture_option("dynamic_contrast", "high", "normal")
    web._api.assert_awaited_once_with("setPictureDBVal", None, settings={"dynamicContrast": "high", "pictureSettingModified": {"normal": True}}, **{"from": "dynamicContrast"})
    with pytest.raises(LGWebError):
        await web.async_write_picture_option("factoryReset", "on", "normal")
    with pytest.raises(LGWebError):
        await web.async_write_picture_option("color_gamut", "wide", "normal")


def test_preferred_color_validation_and_expert_dependency():
    base = {"pictureMode": "normal", "pictureModeSettingsActive": "true", "pictureControlLimitation": "false"}
    assert native_options({**base, "skinColor": -5}) == {"skin_color": "-5"}
    for value in (6, -6, True, None, "nan", 1.5):
        assert not native_options({**base, "skinColor": value})
    assert not native_options({**base, "pictureMode": "expert1", "skinColor": 3, "dynamicColor": "high"})


@pytest.mark.parametrize(("key", "target", "before", "other"), [
    ("min_backlight", "80", "15", "75"), ("max_backlight", "10", "100", "15"),
    ("min_backlight", "20", "15", None),
])
async def test_backlight_range_rejects_crossed_or_unknown_bounds(picture, key, target, before, other):
    picture._read_one = AsyncMock(side_effect=[before, other])
    picture._write_one = AsyncMock()
    with pytest.raises(HomeAssistantError, match="Minimum"):
        await picture.async_set(key, target)
    picture._write_one.assert_not_awaited()


async def test_range_and_hdr_protocol(picture):
    await picture._write_one("min_backlight", "20")
    picture.display.async_send_raw_command.assert_awaited_with("s", "n", 0xAB, query_suffix=" 00 14", use_cache=False)
    picture.display.async_send_raw_command.return_value = "n 01 OKab011ex"
    assert await picture._read_one("max_backlight") == "30"
    await picture._write_one("hdr_picture_mode", "education")
    picture.display.async_send_raw_command.assert_awaited_with("s", "n", 0xC4, query_suffix=" 04", use_cache=False)


async def test_query_suffix_never_treated_as_mutation_and_action_cooldown(monkeypatch):
    import time
    display = LGDisplay("example.invalid")
    reader = asyncio.StreamReader()
    writer = Mock(drain=AsyncMock())
    display._reader, display._writer, display._connected = reader, writer, True
    sent = []
    def reply(data):
        sent.append(data)
        reader.feed_data(b"n 01 OKaf9001x" if b"af" in data else b"k 01 OK00x")
    writer.write.side_effect = reply
    await display.async_send_raw_command("s", "n", 0xAF, query_suffix=" 90 ff")
    assert ("s", "n", 0xAF, " 90 ff") in display._query_cache
    assert await display.async_picture_action("picture_reset")
    assert display._command_not_before > time.monotonic()
    sleep = AsyncMock()
    monkeypatch.setattr("custom_components.lg_rs232_ip.lg_display.asyncio.sleep", sleep)
    await display.async_send_raw_command("s", "n", 0xAF, query_suffix=" 90 ff")
    assert sleep.await_count == 1 and 0 < sleep.await_args.args[0] <= 3
    assert sent.count(b"fk 01 00\r") == 1


async def test_basic_slider_keeps_value_until_refresh_finishes(picture):
    number = LGDisplaySharpnessNumber(picture.display, "LG", "test")
    number._attr_native_value = 25
    started, finish = asyncio.Event(), asyncio.Event()
    async def read(_key):
        started.set()
        await finish.wait()
        return None
    picture.display.async_read_picture_number = read
    task = asyncio.create_task(number.async_update())
    await started.wait()
    assert number.native_value == 25
    finish.set()
    await task
    assert number.native_value is None


async def test_uh5f_black_level_limits_follow_confirmed_context(picture):
    assert picture.options_for("black_level") == ["low", "high"]
    with pytest.raises(HomeAssistantError, match="Unsupported"):
        await picture.async_set("black_level", "auto")
    picture.data = {"black_level": "auto"}
    assert picture.options_for("black_level") == ["auto"]
    picture.display.model_name = "Other signage"
    assert picture.options_for("black_level") == ["low", "high", "auto"]


async def test_picture_mode_returns_after_verified_write_without_full_scan(picture):
    from custom_components.lg_rs232_ip.select import LGDisplayPictureModeSelect

    entity = LGDisplayPictureModeSelect(picture.display, "LG", "test", picture=picture)
    entity.async_write_ha_state = Mock()
    picture.display.async_set_picture_mode = AsyncMock(return_value=True)
    picture.async_request_refresh = AsyncMock(side_effect=AssertionError("Do not wait for all optional settings"))
    await entity.async_select_option("general")
    assert entity.current_option == "general"
    picture.display.async_set_picture_mode.assert_awaited_once_with(1)


async def test_single_picture_number_does_not_invalidate_unrelated_capabilities():
    display = LGDisplay("example.invalid")
    display.async_send_command = AsyncMock(side_effect=[50, 51, 51])
    listener = Mock()
    display.subscribe_picture_settings(listener)
    display._unsupported_until[("s", "n", 0xC4, " ff")] = 12345
    assert await display.async_write_picture_number("contrast", 51)
    assert display._unsupported_until[("s", "n", 0xC4, " ff")] == 12345
    listener.assert_not_called()


async def test_action_interrupts_background_scan_and_old_scan_cannot_overwrite(picture):
    started, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def read(key, **kw):
        calls.append(key)
        if len(calls) == 1:
            started.set()
            await release.wait()
        return "medium"

    picture._read_one = AsyncMock(side_effect=read)
    scan = asyncio.create_task(picture._async_update_data())
    await started.wait()
    action = asyncio.create_task(picture.async_set("gamma", "medium"))
    await asyncio.sleep(0)
    release.set()
    await action
    result = await scan
    assert calls == ["gamma", "gamma"]
    assert result == {"gamma": "medium"}
    picture.web.async_get_picture_options.assert_not_awaited()
