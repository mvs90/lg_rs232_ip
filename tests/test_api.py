"""Cross-integration contract: ownership, fresh power and reload safety."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import pytest
from homeassistant.exceptions import HomeAssistantError
from custom_components.lg_rs232_ip.api import get_display_api
from custom_components.lg_rs232_ip.lg_display import LGDisplay


def api_for(player):
    player.hass.data["lg_rs232_ip"]["test"]["controller"] = player
    return get_display_api(player.hass, "test")


@pytest.mark.asyncio
async def test_adapter_follows_reload_and_never_confirms_missing_display(player):
    api = api_for(player)
    assert await api.async_get_power_status(use_cache=False) is True
    player.hass.data["lg_rs232_ip"].pop("test")
    assert not api.ready
    assert await api.async_get_power_status(use_cache=False) is None
    with pytest.raises(HomeAssistantError):
        async with api.supply_guard():
            pytest.fail("Missing LG cannot authorize a supply cut")
    replacement = Mock(_ha_stopping=False)
    replacement._lg_display.async_get_power_status = AsyncMock(return_value=False)
    player.hass.data["lg_rs232_ip"]["test"] = {"controller": replacement}
    assert await api.async_get_power_status(use_cache=False) is False
    replacement._lg_display.async_get_power_status.assert_awaited_with(use_cache=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("power,allowed", [(None, False), (True, False), (False, True)])
async def test_supply_guard_requires_fresh_confirmed_standby(player, power, allowed):
    api = api_for(player)
    player._lg_display.async_get_power_status.return_value = power
    async with api.supply_guard() as actual:
        assert actual is allowed
        assert player._control_lock.locked()
    player._lg_display.async_get_power_status.assert_awaited_with(use_cache=False)


@pytest.mark.asyncio
async def test_native_download_is_busy_before_display_switch(player):
    api = api_for(player)
    hold = asyncio.Event()
    player._presentation_task = asyncio.create_task(hold.wait())
    try:
        assert api.presentation_active
        with pytest.raises(HomeAssistantError):
            await api.async_power_off()
        with pytest.raises(HomeAssistantError):
            await api.async_begin_external_presentation()
        async with api.supply_guard() as allowed:
            assert not allowed
        player._lg_display.async_power_off.assert_not_awaited()
    finally:
        hold.set()
        await player._presentation_task


@pytest.mark.asyncio
async def test_external_lease_blocks_native_queue_and_supply_cut(player):
    api = api_for(player)
    token = await api.async_begin_external_presentation()
    with pytest.raises(HomeAssistantError):
        await player._enqueue_presentation({"priority": "normal"})
    async with api.supply_guard() as allowed:
        assert not allowed
    await api.async_end_external_presentation("stale")
    assert player.external_owner == token
    await api.async_end_external_presentation(token)
    assert player.external_owner is None


@pytest.mark.asyncio
async def test_queue_waits_for_supply_transition(player):
    api = api_for(player)
    player._lg_display.async_get_power_status.return_value = False
    player._async_present_native = AsyncMock()
    async with api.supply_guard():
        queued = asyncio.create_task(
            player._enqueue_presentation({"priority": "normal"})
        )
        await asyncio.sleep(0)
        assert not queued.done()
    await queued
    if player._presentation_task:
        await player._presentation_task


def test_forgetting_external_supply_does_not_mean_power_off():
    display = LGDisplay("127.0.0.1")
    display.set_power_supply_state(False)
    assert display.is_intentionally_unpowered
    display.set_power_supply_state(None)
    assert not display.is_intentionally_unpowered


def test_api_version_is_explicit(player):
    with pytest.raises(HomeAssistantError):
        get_display_api(player.hass, "test", version=99)


@pytest.mark.asyncio
async def test_controller_has_no_foreign_service_side_effects(player):
    await player.async_turn_on()
    await player.async_select_input(0x91)
    await player.async_turn_off()
    player.hass.services.async_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_display_homekit_target_filter(player):
    from custom_components.lg_rs232_ip.media_player import LGDisplayMediaPlayer

    entity = LGDisplayMediaPlayer(player, SimpleNamespace(entry_id="test", options={}))
    entity.entity_id = "media_player.lg"
    await entity._async_homekit_key(
        SimpleNamespace(
            data={"entity_id": "media_player.other", "key_name": "arrow_up"}
        )
    )
    player._lg_display.async_send_remote_key.assert_not_awaited()
    await entity._async_homekit_key(
        SimpleNamespace(data={"entity_id": "media_player.lg", "key_name": "arrow_up"})
    )
    player._lg_display.async_send_remote_key.assert_awaited_once_with(0x40)


@pytest.mark.asyncio
async def test_alert_state_recovers_without_foreign_device_knowledge(player):
    from custom_components.lg_rs232_ip.alerts import LGDisplayAlertState
    from custom_components.lg_rs232_ip.controller import DisplayController

    alerts = LGDisplayAlertState("test")
    player.hass.data["lg_rs232_ip"]["test"]["alert_state"] = alerts
    player.async_write_ha_state = lambda: DisplayController.async_write_ha_state(player)
    player._lg_display.async_get_power_status.return_value = None
    await player.async_refresh()
    assert alerts.attributes["last_code"] == "display_unresponsive"
    player._lg_display.async_get_power_status.return_value = True
    await player.async_refresh()
    assert alerts.state == "OK"
