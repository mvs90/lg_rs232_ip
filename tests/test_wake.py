"""Wake transactions tolerate lost boot replies and respect newer user intent."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

CLOCK = "custom_components.lg_rs232_ip.controller.monotonic"
SLEEP = "custom_components.lg_rs232_ip.controller.asyncio.sleep"


@pytest.fixture
def clock():
    now = [0.0]

    async def advance(seconds):
        now[0] += seconds

    with patch(CLOCK, side_effect=lambda: now[0]), patch(SLEEP, side_effect=advance):
        yield now


@pytest.mark.asyncio
async def test_wake_retries_transient_tcp_failure_before_confirming_power(player, clock):
    display = player._lg_display
    writes = []

    async def write():
        writes.append(clock[0])
        return len(writes) == 2

    display.async_power_on.side_effect = write
    display.async_get_power_status.side_effect = lambda **_: clock[0] >= 6 or None
    assert await player.async_ensure_on() is True
    assert writes == [0, 5]
    assert player.power is True and clock[0] == 6


@pytest.mark.asyncio
@pytest.mark.parametrize("ack", [True, False])
async def test_lost_or_early_wake_ack_is_read_back_without_restarting_boot(player, clock, ack):
    player._lg_display.async_power_on.return_value = ack
    player._lg_display.async_get_power_status.side_effect = lambda **_: clock[0] >= 4
    assert await player.async_ensure_on() is True
    player._lg_display.async_power_on.assert_awaited_once()
    assert clock[0] == 4


@pytest.mark.asyncio
async def test_power_timeout_is_bounded_and_does_not_select_a_source(player, clock):
    player._config_entry.options["display_wake_timeout"] = 7
    player._lg_display.async_get_power_status.return_value = None
    player._lg_display.async_power_on.return_value = False
    with pytest.raises(HomeAssistantError, match="did not confirm power on.*7 seconds"):
        await player.async_select_input(0x91)
    assert clock[0] == 7
    assert player._lg_display.async_power_on.await_count == 2
    player._lg_display.async_set_input.assert_not_awaited()
    assert player._current_input_id == 0x90
    player._lg_display.async_get_power_status.return_value = True
    await player.async_refresh()
    player._lg_display.async_set_input.assert_not_awaited()  # No late replay.


@pytest.mark.asyncio
async def test_supply_off_is_not_treated_as_transient_network_failure(player):
    player._lg_display.is_intentionally_unpowered = True
    with pytest.raises(HomeAssistantError, match="no external power"):
        await player.async_select_input(0x91)
    player._lg_display.async_get_power_status.assert_not_awaited()
    player._lg_display.async_power_on.assert_not_awaited()
    player._lg_display.async_set_input.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("takeover", ["off", "input", "shutdown"])
async def test_new_action_interrupts_power_wait_without_late_wake_or_input(player, takeover):
    real_sleep = asyncio.sleep
    pending = []
    now = [0.0]
    player._lg_display.async_get_power_status.return_value = False
    player._lg_display.async_power_on.return_value = False

    async def advance(seconds):
        now[0] += seconds
        if not pending:
            if takeover == "input":
                player._lg_display.async_get_power_status.return_value = True
                action = player.async_select_input(0x92, via_app=False)
            elif takeover == "off":
                action = player.async_turn_off()
            else:
                action = player.async_close()
            pending.append(asyncio.create_task(action))
        await real_sleep(0)

    with patch(CLOCK, side_effect=lambda: now[0]), patch(SLEEP, side_effect=advance):
        await player.async_select_input(0x91, via_app=False)
        await asyncio.gather(*pending)
    player._lg_display.async_power_on.assert_awaited_once()
    if takeover == "input":
        player._lg_display.async_set_input.assert_awaited_once_with(0x92)
    else:
        player._lg_display.async_set_input.assert_not_awaited()
    if takeover == "off":
        player._lg_display.async_power_off.assert_not_awaited()  # Already confirmed off.


@pytest.mark.asyncio
async def test_queued_old_turn_on_cannot_wake_after_newer_action(player):
    await player._control_lock.acquire()
    task = asyncio.create_task(player.async_turn_on())
    await asyncio.sleep(0)
    player._cancel_temporary_view()
    player._control_lock.release()
    await task
    player._lg_display.async_power_on.assert_not_awaited()
    player._lg_display.async_get_power_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_native_input_lost_ack_is_confirmed_without_duplicate_write(player):
    player._lg_display.async_set_input.return_value = False
    player._lg_display.async_get_input.return_value = 0x91
    await player.async_select_input(0x91, via_app=False)
    player._lg_display.async_set_input.assert_awaited_once_with(0x91)
    player._lg_display.async_get_input.assert_any_await(use_cache=False)
    assert player._current_input_id == 0x91


@pytest.mark.asyncio
async def test_native_input_retry_after_wake_still_uses_osd_aware_writer(player, clock):
    player._lg_display.async_set_input.side_effect = [False, True]
    await player.async_select_input(0x91, via_app=False)
    assert clock[0] == 5 and player._lg_display.async_set_input.await_count == 2


@pytest.mark.asyncio
async def test_native_input_timeout_is_reported_and_stops_retrying(player, clock):
    player._lg_display.async_set_input.return_value = False
    with pytest.raises(HomeAssistantError, match="HDMI selection within 15 seconds"):
        await player.async_select_input(0x91, via_app=False)
    assert clock[0] == 15 and player._lg_display.async_set_input.await_count == 3


@pytest.mark.asyncio
async def test_real_wake_deadline_also_bounds_a_stalled_query(player):
    player._config_entry.options["display_wake_timeout"] = 0.02
    blocked = asyncio.Event()
    player._lg_display.async_get_power_status = AsyncMock(side_effect=lambda **_: None)

    async def wait(**_):
        await blocked.wait()

    player._lg_display.async_get_power_status.side_effect = wait
    with pytest.raises(HomeAssistantError, match="did not confirm power on"):
        await player.async_ensure_on()
    player._lg_display.async_power_on.assert_not_awaited()


@pytest.mark.asyncio
async def test_eof_during_command_uses_connection_backoff_without_error_log(caplog):
    from custom_components.lg_rs232_ip.lg_display import LGDisplay

    display = LGDisplay("example.invalid")
    display._reader = asyncio.StreamReader()
    display._reader.feed_eof()
    writer = Mock(drain=AsyncMock(), wait_closed=AsyncMock())
    display._writer, display._connected = writer, True
    assert await display.async_get_power_status(use_cache=False) is None
    assert not display.is_connected
    writer.close.assert_called_once()
    assert not [record for record in caplog.records if record.levelno >= 40]
    with patch("asyncio.open_connection", new_callable=AsyncMock) as connect:
        assert not await display.async_power_on()
        connect.assert_not_awaited()  # Backoff applies after EOF as after reset.


@pytest.mark.asyncio
async def test_native_source_ack_survives_an_unanswered_followup_query(player):
    player._lg_display.async_get_input.return_value = None
    await player.async_select_input(0x91, via_app=False)
    assert player._current_input_id == 0x91
    assert player._source == 'HDMI 2'


@pytest.mark.asyncio
async def test_power_off_during_startup_retries_the_lost_tcp_reply(player, clock):
    player._lg_display.async_get_power_status.return_value = None
    player._lg_display.async_power_off.side_effect = [False, True]
    await player.async_turn_off()
    assert clock[0] == 5 and player._lg_display.async_power_off.await_count == 2
    player._lg_display.async_power_on.assert_not_awaited()


@pytest.mark.asyncio
async def test_lost_off_ack_does_not_repeat_after_confirmed_standby(player, clock):
    player._lg_display.async_get_power_status.side_effect = lambda **_: clock[0] < 4
    player._lg_display.async_power_off.return_value = False
    await player.async_turn_off()
    assert player.power is False and clock[0] == 4
    player._lg_display.async_power_off.assert_awaited_once()


@pytest.mark.asyncio
async def test_off_failure_has_a_bounded_honest_error(player, clock):
    player._config_entry.options['display_wake_timeout'] = 6
    player._lg_display.async_power_off.return_value = False
    with pytest.raises(HomeAssistantError, match='did not confirm power off.*6 seconds'):
        await player.async_turn_off()
    assert clock[0] == 6
