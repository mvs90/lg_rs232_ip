"""Boot setting readback, safe preparation and throttled real-frame preview."""

import asyncio
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from PIL import Image
import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.lg_rs232_ip.boot_image import (
    prepare_boot_jpeg,
    save_boot_image,
    async_prepare_boot_image,
)
from custom_components.lg_rs232_ip.camera import LGDisplayPreview
from custom_components.lg_rs232_ip.lg_display import LGDisplay
from custom_components.lg_rs232_ip.switch import LGDisplayBootLogoSwitch
from custom_components.lg_rs232_ip.web_manager import LGWebError


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("n 01 OKa301x", True),
        ("n 01 OKa300x", False),
        ("n 01 NGa301x", None),
        ("n 01 OKa901x", None),
        ("n 01 OKa302x", None),
        (None, None),
    ],
)
async def test_boot_logo_read_validates_echo(reply, expected):
    display = LGDisplay("example.test")
    display.async_send_raw_command = AsyncMock(return_value=reply)
    assert await display.async_get_boot_logo() is expected
    display.async_send_raw_command.assert_awaited_once_with(
        "s", "n", 0xA3, query_suffix=" ff", use_cache=False
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("enabled", "reply", "expected"),
    [
        (True, "n 01 OKa301x", True),
        (False, "n 01 OKa300x", True),
        (True, "n 01 OKa300x", False),
        (False, "n 01 OKa900x", False),
    ],
)
async def test_boot_write_checks_exact_parameter_and_value(enabled, reply, expected):
    display = LGDisplay("example.test")
    display.async_send_raw_command = AsyncMock(return_value=reply)
    assert await display.async_set_boot_logo(enabled) is expected
    display.async_send_raw_command.assert_awaited_once_with(
        "s", "n", 0xA3, query_suffix=f" {int(enabled):02x}", use_cache=False
    )


@pytest.mark.asyncio
async def test_boot_switch_requires_fresh_confirmation_and_never_wakes():
    display = AsyncMock()
    display.async_get_power_status.return_value = True
    display.async_set_boot_logo.return_value = True
    display.async_get_boot_logo.return_value = False
    switch = LGDisplayBootLogoSwitch(display, "Display", "test")
    switch.async_write_ha_state = Mock()
    with pytest.raises(HomeAssistantError, match="not confirmed"):
        await switch.async_turn_on()
    display.async_get_power_status.return_value = False
    with pytest.raises(HomeAssistantError, match="awake"):
        await switch.async_turn_on()
    display.async_power_on.assert_not_awaited()


def source_image(size=(100, 200), mode="RGBA"):
    image = Image.new(mode, size, "red")
    output = BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def test_boot_conversion_fits_without_distortion_or_metadata():
    data = prepare_boot_jpeg(source_image())
    with Image.open(BytesIO(data)) as image:
        assert image.format == "JPEG"
        assert image.size == (1920, 1080)
        assert not image.getexif()
        assert not image.info.get("progressive")
        assert image.getpixel((0, 0)) == (0, 0, 0)
        assert image.getpixel((960, 540))[0] > 240


@pytest.mark.parametrize("data", [b"not-an-image", b"", b"x" * (5 * 1024 * 1024 + 1)])
def test_boot_preparation_rejects_invalid_or_oversized_input(data):
    with pytest.raises(ValueError):
        prepare_boot_jpeg(data)


def test_boot_preparation_rejects_large_decoded_image():
    with pytest.raises(ValueError):
        prepare_boot_jpeg(source_image((5000, 4001), "RGB"))


def test_boot_write_is_scoped_atomic_and_replaces_only_generated_file(tmp_path):
    relative = save_boot_image(str(tmp_path), "test", b"first")
    assert relative == "lg_rs232_ip/test/LG_MONITOR/bootlogo.jpg"
    unrelated = tmp_path / "family.jpg"
    unrelated.write_bytes(b"keep")
    save_boot_image(str(tmp_path), "test", b"second")
    assert (tmp_path / relative).read_bytes() == b"second"
    assert unrelated.read_bytes() == b"keep"
    assert not list((tmp_path / relative).parent.glob(".bootlogo-*"))
    with pytest.raises(ValueError):
        save_boot_image(str(tmp_path), "../escape", b"image")


def test_boot_write_rejects_symlink_escape(tmp_path):
    root = tmp_path / "media"
    root.mkdir()
    (root / "lg_rs232_ip").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        save_boot_image(str(root), "test", b"image")


@pytest.mark.asyncio
async def test_prepare_service_returns_usb_instructions_without_install_claim(
    player, tmp_path
):
    player.hass.config.media_dirs = {"local": str(tmp_path)}
    player.hass.async_add_executor_job = AsyncMock(
        side_effect=lambda func, *args: func(*args)
    )
    player._async_download_native_image = AsyncMock(return_value=source_image())
    result = await async_prepare_boot_image(
        player, "media-source://media_source/local/input.png"
    )
    assert result["installed_on_display"] is False
    assert result["media_id"].endswith("/lg_rs232_ip/test/LG_MONITOR/bootlogo.jpg")
    assert (tmp_path / "lg_rs232_ip/test/LG_MONITOR/bootlogo.jpg").is_file()
    player._lg_display.async_power_on.assert_not_awaited()


@pytest.fixture
def preview():
    display = AsyncMock()
    display.async_get_power_status.return_value = True
    web = AsyncMock()
    web.async_capture.return_value = b"real-frame"
    entity = LGDisplayPreview(
        SimpleNamespace(entry_id="test", options={"preview_interval": 30}), display, web
    )
    entity.hass = Mock()
    entity.async_write_ha_state = Mock()
    with patch(
        "custom_components.lg_rs232_ip.camera.async_call_later", return_value=Mock()
    ):
        yield entity, display, web


@pytest.mark.asyncio
async def test_preview_clients_share_one_throttled_capture(preview):
    entity, display, web = preview
    results = await asyncio.gather(*(entity.async_camera_image() for _ in range(10)))
    assert results == [b"real-frame"] * 10
    web.async_capture.assert_awaited_once_with(720)
    assert entity.extra_state_attributes["last_capture"] is not None
    assert not entity.is_streaming


@pytest.mark.asyncio
async def test_preview_failure_drops_stale_frame_and_recovers(preview):
    entity, display, web = preview
    await entity.async_update()
    web.async_capture.side_effect = LGWebError("private-device-response")
    entity._next_capture = 0
    await entity.async_update()
    assert entity._image is None
    assert not entity.available
    assert entity.extra_state_attributes["preview_error"] == "capture_failed"
    web.async_capture.side_effect = None
    entity._next_capture = 0
    await entity.async_update()
    assert entity.available


@pytest.mark.asyncio
@pytest.mark.parametrize("power", [False, None])
async def test_preview_never_wakes_or_captures_off_unknown_display(preview, power):
    entity, display, web = preview
    display.async_get_power_status.return_value = power
    assert await entity.async_camera_image() is None
    web.async_capture.assert_not_awaited()
    display.async_power_on.assert_not_awaited()


@pytest.mark.asyncio
async def test_camera_off_clears_frame_and_prevents_background_collection(preview):
    entity, display, web = preview
    await entity.async_update()
    await entity.async_turn_off()
    entity._next_capture = 0
    assert await entity.async_camera_image() is None
    assert entity._image is None
    assert web.async_capture.await_count == 1
    await entity.async_turn_on()
    assert web.async_capture.await_count == 2
    display.async_power_off.assert_not_awaited()


@pytest.mark.asyncio
async def test_off_during_capture_does_not_publish_late_result(preview):
    entity, display, web = preview
    started, finish = asyncio.Event(), asyncio.Event()

    async def capture(_):
        started.set()
        await finish.wait()
        return b"late-frame"

    web.async_capture.side_effect = capture
    task = asyncio.create_task(entity.async_update())
    await started.wait()
    await entity.async_turn_off()
    finish.set()
    await task
    assert entity._image is None
    assert entity._captured_at is None


@pytest.mark.asyncio
async def test_camera_timer_and_frame_are_removed_on_unload(preview):
    entity, display, web = preview
    from homeassistant.components.camera import Camera

    await entity.async_update()
    timer = entity._timer_unsub
    with patch.object(Camera, "async_will_remove_from_hass", new_callable=AsyncMock):
        await entity.async_will_remove_from_hass()
    timer.assert_called_once()
    entity._next_capture = 0
    assert await entity.async_camera_image() is None
    assert web.async_capture.await_count == 1
