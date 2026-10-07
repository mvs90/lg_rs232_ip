"""Exercise the real HA entity-service registry, not just direct method calls."""

from contextlib import asynccontextmanager
from datetime import timedelta
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import EntityPlatform
from custom_components.lg_rs232_ip.media_player import async_setup_entry
from custom_components.lg_rs232_ip.controller import DisplayController


@pytest.mark.asyncio
async def test_real_entity_services_target_registered_display(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    display = Mock()
    display.async_get_input = AsyncMock(return_value=0x91)
    display.async_send_remote_key = AsyncMock(return_value=True)
    entry = SimpleNamespace(entry_id="display", options={}, title="Display")
    hass.data["lg_rs232_ip"] = {"display": {"lg_display": display, "name": "Display"}}
    hass.data["lg_rs232_ip"]["display"]["controller"] = DisplayController(
        hass, entry, display
    )
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
        "custom_components.lg_rs232_ip.media_player.async_get_current_platform",
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
        player.controller.async_select_app_view = AsyncMock()
        await hass.services.async_call(
            "lg_rs232_ip",
            "show_view",
            {
                "entity_id": player.entity_id,
                "view": "hdmi_full",
                "transition": "smooth",
            },
            blocking=True,
        )
        player.controller.async_select_app_view.assert_awaited_once_with(
            "hdmi_full", transition="smooth", duration=0
        )
        for theme in ("morning", ""):
            player.controller.async_select_app_view.reset_mock()
            await hass.services.async_call(
                "lg_rs232_ip", "show_view",
                {"entity_id": player.entity_id, "view": "dashboard", "theme": theme},
                blocking=True,
            )
            player.controller.async_select_app_view.assert_awaited_once_with(
                "dashboard", transition="none", duration=0,
                **({"theme": theme} if theme else {}),
            )
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                "lg_rs232_ip",
                "show_view",
                {
                    "entity_id": player.entity_id,
                    "view": "pip_view",
                    "transition": "unbounded",
                },
                blocking=True,
            )
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                "lg_rs232_ip",
                "show_native_video",
                {"entity_id": player.entity_id, "media_id": "test", "duration": 0},
                blocking=True,
            )
        platform_api = SimpleNamespace(configure_wall=AsyncMock(), refresh=AsyncMock())
        hass.data["lg_rs232_ip"]["display"]["display_app"] = SimpleNamespace(
            resident_connected=True, platform=platform_api
        )
        guard = []

        @asynccontextmanager
        async def suppress():
            guard.append("enter")
            try:
                yield
            finally:
                guard.append("exit")

        display.async_suppress_osd_for_switch = suppress
        await hass.services.async_call(
            "lg_rs232_ip",
            "configure_video_wall",
            {
                "entity_id": player.entity_id,
                "enabled": True,
                "rows": 2,
                "columns": 2,
                "tile_id": 1,
                "natural_mode": False,
            },
            blocking=True,
        )
        platform_api.configure_wall.assert_awaited_once_with(
            {"enabled": True, "row": 2, "column": 2, "tileId": 1, "naturalMode": False}
        )
        platform_api.refresh.assert_awaited_once()
        assert guard == ["enter", "exit"]
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                "lg_rs232_ip",
                "configure_video_wall",
                {"entity_id": player.entity_id, "enabled": True, "rows": 16},
                blocking=True,
            )
        hass.data["lg_rs232_ip"]["display"].pop("display_app")
        assert not hass.services.has_service("lg_rs232_ip", "announce")
        assert hass.services.has_service("lg_rs232_ip", "show_native_image")
        for service in ("show_native_video", "show_stream", "show_website"):
            assert hass.services.has_service("lg_rs232_ip", service)
        player.async_show_native_video = AsyncMock()
        player.async_show_stream = AsyncMock()
        player.async_show_website = AsyncMock()
        for service, field in (
            ("show_native_video", "media_id"),
            ("show_stream", "media_id"),
            ("show_website", "url"),
        ):
            await hass.services.async_call(
                "lg_rs232_ip",
                service,
                {
                    "entity_id": player.entity_id,
                    field: "https://example.test/content",
                    "duration": 30,
                },
                blocking=True,
            )
            getattr(player, "async_" + service).assert_awaited_once()
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
        player.async_prepare_ism_media = AsyncMock(return_value={"installed_on_display": False, "import_method": "usb"})
        response = await hass.services.async_call(
            "lg_rs232_ip", "prepare_ism_media",
            {"entity_id": player.entity_id, "media_ids": ["media-source://media_source/local/photo.jpg"]},
            blocking=True, return_response=True,
        )
        assert response[player.entity_id]["import_method"] == "usb"
        player.async_prepare_ism_media.assert_awaited_once_with(media_ids=["media-source://media_source/local/photo.jpg"], media_type="image", media_directory="local")
        schedules = SimpleNamespace(async_change=AsyncMock())
        maintenance = SimpleNamespace(async_set_timezone=AsyncMock(), async_configure_dst=AsyncMock(), async_get_timezones=AsyncMock(return_value={"timezones": [{"ZoneID": "Europe/Berlin"}]}))
        hass.data["lg_rs232_ip"]["display"].update(native_schedules=schedules, maintenance=maintenance)
        for action, kwargs in (
            ("add_power_schedule", {"kind": "power_on", "time": "07:00", "repeat": "weekdays"}),
            ("add_brightness_schedule", {"time": "07:00", "backlight": 75}),
            ("remove_native_schedule", {"kind": "power_on", "schedule_id": "mon@07:00"}),
            ("set_timezone", {"continent": "Europe", "country": "DE", "timezone": "Europe/Berlin"}),
            ("configure_dst", {"enabled": False}),
        ):
            await hass.services.async_call("lg_rs232_ip", action, {"entity_id": player.entity_id, **kwargs}, blocking=True)
        assert schedules.async_change.await_count == 3
        schedules.async_change.assert_awaited_with("power_on", schedule_id="mon@07:00")
        maintenance.async_set_timezone.assert_awaited_once_with("Europe", "DE", "Europe/Berlin")
        maintenance.async_configure_dst.assert_awaited_once_with(False)
        response = await hass.services.async_call("lg_rs232_ip", "get_timezones", {"entity_id": player.entity_id, "country": "DE"}, blocking=True, return_response=True)
        assert response[player.entity_id]["timezones"][0]["ZoneID"] == "Europe/Berlin"
        for action, kwargs in (("add_brightness_schedule", {"time": "07:00", "backlight": 1.5}), ("configure_dst", {"enabled": True, "start_hour": 1.5})):
            with pytest.raises(vol.Invalid):
                await hass.services.async_call("lg_rs232_ip", action, {"entity_id": player.entity_id, **kwargs}, blocking=True)
    finally:
        await hass.async_stop(force=True)
