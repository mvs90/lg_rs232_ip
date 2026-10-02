"""Native presentation ownership, cancellation and restoration regressions."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from custom_components.lg_rs232_ip.web_manager import LGWebError

HDMI = "com.webos.app.hdmi1"
DSMP = "com.webos.app.dsmp"
ASSET = {
    "name": "ha_lg_" + "a" * 32 + ".png",
    "path": "/mnt/lg/appstore/signage/ha_lg_" + "a" * 32 + ".png",
}
REQUEST = dict(
    kind="native_image",
    media_id="http://example.test/image.png",
    duration=0,
    priority="normal",
)


@pytest.fixture
def native(player):
    web = AsyncMock()
    web.async_upload_image.return_value = ASSET
    web.async_play_image.return_value = None
    web.async_foreground_app.side_effect = [HDMI, HDMI, DSMP, HDMI]
    player.hass.data["lg_rs232_ip"]["test"]["web_manager"] = web
    player._async_download_native_image = AsyncMock(return_value=b"image")
    return player, web


@pytest.mark.asyncio
async def test_native_requires_opt_in(player):
    with pytest.raises(ServiceValidationError, match="Enable"):
        await player.async_show_toast("Test")
    with pytest.raises(ServiceValidationError, match="Enable"):
        await player.async_show_native_image("test")


@pytest.mark.asyncio
async def test_toast_uses_native_backend_without_source_change(native):
    player, web = native
    await player.async_show_toast("Hello")
    web.async_toast.assert_awaited_once_with("Hello")
    player._lg_display.async_set_input.assert_not_awaited()
    assert not player._presentation_active


@pytest.mark.asyncio
async def test_toast_no_wake_and_quiet_hours(native):
    player, web = native
    player._lg_display.async_get_power_status.return_value = False
    with pytest.raises(HomeAssistantError, match="awake"):
        await player.async_show_toast("Hello")
    player._config_entry.options["quiet_hours_enabled"] = True
    with patch(
        "custom_components.lg_rs232_ip.controls.in_quiet_hours", return_value=True
    ):
        with pytest.raises(ServiceValidationError, match="quiet"):
            await player.async_show_toast("Hello")
    web.async_toast.assert_not_awaited()
    player._lg_display.async_power_on.assert_not_awaited()


@pytest.mark.asyncio
async def test_native_restores_even_though_rs232_still_reports_hdmi(native):
    player, web = native
    await player._async_present_native_image(REQUEST)
    player._lg_display.async_set_input.assert_awaited_once_with(0x90)
    web.async_delete_image.assert_awaited_once_with(ASSET)
    assert not player._presentation_active
    assert player._presentation_error is None


@pytest.mark.asyncio
async def test_native_respects_physical_source_change(native):
    player, web = native
    web.async_foreground_app.side_effect = [HDMI, HDMI, "com.webos.app.hdmi2"]
    await player._async_present_native_image(REQUEST)
    player._lg_display.async_set_input.assert_not_awaited()
    web.async_delete_image.assert_awaited_once_with(ASSET)


@pytest.mark.asyncio
async def test_native_cancels_if_source_changed_during_upload(native):
    player, web = native
    web.async_foreground_app.side_effect = [HDMI, "com.webos.app.hdmi2"]
    with pytest.raises(HomeAssistantError, match="changed"):
        await player._async_present_native_image(REQUEST)
    web.async_play_image.assert_not_awaited()
    web.async_delete_image.assert_awaited_once_with(ASSET)
    player._lg_display.async_set_input.assert_not_awaited()


@pytest.mark.asyncio
async def test_native_will_not_disrupt_existing_native_content(native):
    player, web = native
    web.async_foreground_app.side_effect = [DSMP]
    with pytest.raises(HomeAssistantError, match="external input"):
        await player._async_present_native_image(REQUEST)
    web.async_upload_image.assert_not_awaited()


@pytest.mark.asyncio
async def test_native_retains_image_if_restoration_fails(native):
    player, web = native
    player._lg_display.async_set_input.return_value = False
    await player._async_present_native_image(REQUEST)
    web.async_delete_image.assert_not_awaited()
    assert "retained" in player._presentation_error
    assert not player._presentation_active


@pytest.mark.asyncio
async def test_launch_failure_still_restores_and_cleans(native):
    player, web = native
    web.async_play_image.side_effect = LGWebError("launch not confirmed")
    with pytest.raises(LGWebError):
        await player._async_present_native_image(REQUEST)
    player._lg_display.async_set_input.assert_awaited_once_with(0x90)
    web.async_delete_image.assert_awaited_once_with(ASSET)


@pytest.mark.asyncio
async def test_cancel_during_upload_waits_for_result_and_deletes(native):
    player, web = native
    started, finish = asyncio.Event(), asyncio.Event()

    async def upload(_):
        started.set()
        await finish.wait()
        return ASSET

    web.async_upload_image.side_effect = upload
    task = asyncio.create_task(player._async_present_native_image(REQUEST))
    await started.wait()
    task.cancel()
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    web.async_play_image.assert_not_awaited()
    web.async_delete_image.assert_awaited_once_with(ASSET)
    assert not player._presentation_active


@pytest.mark.asyncio
async def test_cancel_during_play_waits_then_restores(native):
    player, web = native
    started, finish = asyncio.Event(), asyncio.Event()

    async def play(_):
        started.set()
        await finish.wait()

    web.async_play_image.side_effect = play
    task = asyncio.create_task(player._async_present_native_image(REQUEST))
    await started.wait()
    task.cancel()
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    player._lg_display.async_set_input.assert_awaited_once_with(0x90)
    web.async_delete_image.assert_awaited_once_with(ASSET)


@pytest.mark.asyncio
async def test_native_off_by_default_does_not_upload(native):
    player, web = native
    player._lg_display.async_get_power_status.return_value = False
    with pytest.raises(HomeAssistantError, match="wake is disabled"):
        await player._async_present_native_image(REQUEST)
    web.async_upload_image.assert_not_awaited()


@pytest.mark.asyncio
async def test_native_optional_wake_restores_confirmed_standby(native):
    player, web = native
    player._config_entry.options["notification_wake_display"] = True
    player._async_ensure_display_on_after_power_restore = AsyncMock()
    player._lg_display.async_get_power_status.side_effect = [False, True, True, False]
    from unittest.mock import Mock

    player._schedule_power_supply_off = Mock()
    await player._async_present_native_image(REQUEST)
    player._lg_display.async_power_off.assert_awaited_once()
    player._schedule_power_supply_off.assert_called_once()
    web.async_delete_image.assert_awaited_once_with(ASSET)


@pytest.mark.asyncio
async def test_image_download_failure_is_sanitized(player):
    player._async_resolve_media = AsyncMock(
        side_effect=ValueError("private-signed-url")
    )
    with pytest.raises(HomeAssistantError) as err:
        await player._async_download_native_image("private-signed-url")
    assert "private-signed-url" not in str(err.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url", ["file:///etc/passwd", "http://user:pass@example.test/image.png"]
)
async def test_native_image_rejects_non_http_or_embedded_credentials(player, url):
    player._async_resolve_media = AsyncMock(return_value=(url, "image"))
    with pytest.raises(HomeAssistantError, match="Cannot load"):
        await player._async_download_native_image(url)


@pytest.mark.asyncio
@pytest.mark.parametrize("known_length", [True, False])
async def test_native_download_size_is_bounded_even_without_content_length(
    player, known_length
):
    from unittest.mock import Mock
    from custom_components.lg_rs232_ip.native_presentations import MAX_IMAGE_BYTES

    player._async_resolve_media = AsyncMock(
        return_value=("http://example.test/image.png", "image")
    )
    response = Mock()
    response.content_length = MAX_IMAGE_BYTES + 1 if known_length else None

    async def chunks(_):
        yield b"x" * MAX_IMAGE_BYTES
        yield b"x"

    response.content.iter_chunked = chunks
    session = Mock()
    context = AsyncMock()
    context.__aenter__.return_value = response
    session.get.return_value = context
    with patch(
        "custom_components.lg_rs232_ip.native_presentations.async_get_clientsession",
        return_value=session,
    ):
        with pytest.raises(HomeAssistantError, match="5 MiB"):
            await player._async_download_native_image("http://example.test/image.png")


@pytest.mark.asyncio
async def test_repeated_clear_does_not_interrupt_upload_cleanup(native):
    player, web = native
    started, finish = asyncio.Event(), asyncio.Event()

    async def upload(_):
        started.set()
        await finish.wait()
        return ASSET

    web.async_upload_image.side_effect = upload
    player._presentation_queue.append(REQUEST)
    player._presentation_task = asyncio.create_task(player._async_presentations())
    await started.wait()
    first = asyncio.create_task(player._async_cancel_presentations())
    await asyncio.sleep(0)
    second = asyncio.create_task(player._async_cancel_presentations())
    await asyncio.sleep(0)
    finish.set()
    await asyncio.gather(first, second)
    web.async_delete_image.assert_awaited_once_with(ASSET)
    assert not player._presentation_active
