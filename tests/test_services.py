"""Exercise the real HA entity-service registry, not just direct method calls."""

from datetime import timedelta
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import EntityPlatform
from custom_components.lg_rs232_ip.media_player import async_setup_entry


@pytest.mark.asyncio
async def test_real_entity_services_target_registered_display(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    display = Mock()
    display.async_get_input = AsyncMock(return_value=0x91)
    display.async_send_remote_key = AsyncMock(return_value=True)
    entry = SimpleNamespace(entry_id="display", options={})
    hass.data["lg_rs232_ip"] = {"display": {"lg_display": display, "name": "Display"}}
    platform = EntityPlatform(
        hass=hass,
        logger=logging.getLogger(__name__),
        domain="media_player",
        platform_name="lg_rs232_ip",
        platform=None,
        scan_interval=timedelta(seconds=60),
        entity_namespace=None,
    )
    added = []
    with patch(
        "custom_components.lg_rs232_ip.media_player.entity_platform.async_get_current_platform",
        return_value=platform,
    ):
        await async_setup_entry(hass, entry, added.extend)
    player = added[0]
    player.hass = hass
    player.entity_id = "media_player.display"
    player.platform = platform
    player.async_write_ha_state = Mock()
    platform.entities[player.entity_id] = player
    platform.domain_entities[player.entity_id] = player
    platform.domain_platform_entities[player.entity_id] = player
    hass.states.async_set(player.entity_id, "on")
    try:
        await hass.services.async_call(
            "lg_rs232_ip",
            "send_remote_command",
            {"entity_id": player.entity_id, "command": "up"},
            blocking=True,
        )
        display.async_send_remote_key.assert_awaited_once_with(0x40)
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                "lg_rs232_ip",
                "show_content",
                {"entity_id": player.entity_id, "media_id": "test", "duration": 0},
                blocking=True,
            )
        assert hass.services.has_service("lg_rs232_ip", "announce")
        assert hass.services.has_service("lg_rs232_ip", "show_native_image")
        web = AsyncMock()
        hass.data["lg_rs232_ip"]["display"]["web_manager"] = web
        display.async_get_power_status = AsyncMock(return_value=True)
        await hass.services.async_call(
            "lg_rs232_ip",
            "show_toast",
            {"entity_id": player.entity_id, "message": "Hello"},
            blocking=True,
        )
        web.async_toast.assert_awaited_once_with("Hello")
        player.async_prepare_boot_image = AsyncMock(
            return_value={"installed_on_display": False}
        )
        response = await hass.services.async_call(
            "lg_rs232_ip",
            "prepare_boot_image",
            {
                "entity_id": player.entity_id,
                "media_id": "media-source://media_source/local/logo.png",
            },
            blocking=True,
            return_response=True,
        )
        assert response[player.entity_id]["installed_on_display"] is False
    finally:
        await hass.async_stop(force=True)
