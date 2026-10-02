from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock
import asyncio
import pytest
from homeassistant.core import State
from homeassistant.components.media_player import (
    MediaPlayerEntityFeature as Feature,
)
from custom_components.lg_rs232_ip.controller import DisplayController


@pytest.fixture
def player():
    states = {
        "media_player.apple_tv": State(
            "media_player.apple_tv",
            "idle",
            {
                "supported_features": int(
                    Feature.PLAY
                    | Feature.PAUSE
                    | Feature.STOP
                    | Feature.PLAY_MEDIA
                    | Feature.NEXT_TRACK
                    | Feature.SEEK
                )
            },
        )
    }
    hass = Mock()
    hass.states.get.side_effect = states.get
    hass.services.async_call = AsyncMock()
    hass.async_create_task.side_effect = asyncio.create_task
    hass.data = {"lg_rs232_ip": {"test": {"sync_automation_enabled": True}}}
    entry = SimpleNamespace(
        entry_id="test",
        options={
            "linked_media_player_entity_id": "media_player.apple_tv",
            "standby_no_signal_seconds": 120,
            "standby_idle_seconds": 900,
        },
    )
    display = Mock(is_intentionally_unpowered=False)
    display.async_get_power_status = AsyncMock(return_value=True)
    display.async_get_input = AsyncMock(return_value=0x90)
    display.async_get_signal_status = AsyncMock(return_value=False)
    display.async_get_volume = AsyncMock(return_value=30)
    display.async_send_command = AsyncMock(return_value=1)
    display.async_set_input = AsyncMock(return_value=True)
    display.async_power_on = AsyncMock(return_value=True)
    display.async_send_remote_key = AsyncMock(return_value=True)
    display.async_power_off = AsyncMock(return_value=True)
    display.async_suppress_osd_for_switch = Mock(return_value=AsyncMock())
    display.osd_restore_error = False
    display.async_restore_pending_osd = AsyncMock()
    p = DisplayController(hass, entry, display)
    p.entity_id = "media_player.display"
    p._current_input_id = 0x90
    p.async_write_ha_state = Mock()
    return p
