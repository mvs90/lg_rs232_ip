"""Preserve user OSD state through temporary source suppression."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from custom_components.lg_rs232_ip.lg_display import LGDisplay


@pytest.fixture
def display():
    d = LGDisplay("example.test")
    d.suppress_osd_during_switch = True
    return d


@pytest.mark.asyncio
@pytest.mark.parametrize("initial", [0, None, 2])
async def test_disabled_unknown_or_invalid_osd_is_never_enabled(display, initial):
    display.async_send_command = AsyncMock(side_effect=[initial, 0x91])
    assert await display.async_set_input(0x91)
    assert [c.args for c in display.async_send_command.await_args_list] == [
        ("k", "l", 255),
        ("x", "b", 0x91),
    ]
    assert display.async_send_command.await_args_list[0].kwargs == {"use_cache": False}


@pytest.mark.asyncio
async def test_enabled_osd_restored_after_switch(display):
    display.async_send_command = AsyncMock(side_effect=[1, 0, 0x91, 0, 1])
    with patch(
        "custom_components.lg_rs232_ip.lg_display.asyncio.sleep", new_callable=AsyncMock
    ):
        assert await display.async_set_input(0x91)
    assert [c.args for c in display.async_send_command.await_args_list] == [
        ("k", "l", 255),
        ("k", "l", 0),
        ("x", "b", 0x91),
        ("k", "l", 255),
        ("k", "l", 1),
    ]
    assert not display.osd_restore_error


@pytest.mark.asyncio
async def test_disabled_option_does_not_touch_osd(display):
    display.suppress_osd_during_switch = False
    display.async_send_command = AsyncMock(return_value=0x91)
    assert await display.async_set_input(0x91)
    display.async_send_command.assert_awaited_once_with("x", "b", 0x91)


@pytest.mark.asyncio
async def test_failed_switch_restores_osd(display):
    display.async_send_command = AsyncMock(side_effect=[1, 0, None, 0, 1])
    with patch(
        "custom_components.lg_rs232_ip.lg_display.asyncio.sleep", new_callable=AsyncMock
    ):
        assert not await display.async_set_input(0x91)
    assert display.async_send_command.await_args.args == ("k", "l", 1)


@pytest.mark.asyncio
async def test_cancellation_inside_transition_restores_osd(display):
    display.async_send_command = AsyncMock(side_effect=[1, 0, 0, 1])
    with patch(
        "custom_components.lg_rs232_ip.lg_display.asyncio.sleep", new_callable=AsyncMock
    ):
        with pytest.raises(asyncio.CancelledError):
            async with display.async_suppress_osd_for_switch():
                raise asyncio.CancelledError
    assert display.async_send_command.await_args.args == ("k", "l", 1)


@pytest.mark.asyncio
async def test_manual_osd_change_wins_over_temporary_restore(display):
    display.async_send_command = AsyncMock(side_effect=[1, 0, 0])
    manual = None
    real_sleep = asyncio.sleep
    with patch(
        "custom_components.lg_rs232_ip.lg_display.asyncio.sleep", new_callable=AsyncMock
    ):
        async with display.async_suppress_osd_for_switch():
            manual = asyncio.create_task(display.async_set_osd_select(False))
            # Run the explicit request up to its transition-lock wait.
            await real_sleep(0)
        assert await manual
    assert ("k", "l", 1) not in [
        c.args for c in display.async_send_command.await_args_list
    ]


@pytest.mark.asyncio
async def test_unknown_restore_state_does_not_blindly_enable(display):
    display.async_send_command = AsyncMock(side_effect=[1, 0, 0x91, None])
    with patch(
        "custom_components.lg_rs232_ip.lg_display.asyncio.sleep", new_callable=AsyncMock
    ):
        assert await display.async_set_input(0x91)
    assert display.osd_restore_error
    assert ("k", "l", 1) not in [
        c.args for c in display.async_send_command.await_args_list
    ]


@pytest.mark.asyncio
async def test_native_unlock_rejection_preserves_ownership_until_hdmi_return(display):
    # Start: on -> off -> native app rejects unlock. Return: still off, but ours.
    display.async_send_command = AsyncMock(side_effect=[1, 0, 0, None, 0, 0x90, 0, 1])
    with patch(
        "custom_components.lg_rs232_ip.lg_display.asyncio.sleep", new_callable=AsyncMock
    ):
        async with display.async_suppress_osd_for_switch():
            pass
        assert display.osd_restore_error
        assert display._osd_pending_restore_revision == 0
        assert await display.async_set_input(0x90)
    assert not display.osd_restore_error
    assert display._osd_pending_restore_revision is None
    assert display.async_send_command.await_args.args == ("k", "l", 1)


@pytest.mark.asyncio
async def test_user_off_clears_pending_restore_ownership(display):
    display._osd_pending_restore_revision = 0
    display.async_send_command = AsyncMock(return_value=0)
    assert await display.async_set_osd_select(False)
    await display.async_restore_pending_osd()
    display.async_send_command.assert_awaited_once_with("k", "l", 0)
    assert display._osd_pending_restore_revision is None
