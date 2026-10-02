"""Paired app boundary, settings ownership, recovery and real HA route tests."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest

from custom_components.lg_rs232_ip.display_app import (
    DisplayAppManager,
    DisplayAppView,
    SI_APP_ID,
    validate_base_url,
)
from custom_components.lg_rs232_ip.web_manager import LGWebError, LGWebManager

HDMI = "com.webos.app.hdmi1"
ORIGINAL = dict(
    serverIpPort="0",
    siServerIp="0.0.0.0",
    secureConnection="off",
    appLaunchMode="none",
    fqdnAddr="http://",
    fqdnMode="off",
    appType="zip",
)


@pytest.fixture
async def app(tmp_path, player):
    hass = HomeAssistant(str(tmp_path))
    entry = SimpleNamespace(
        entry_id="test",
        options={
            "display_app_enabled": True,
            "display_app_mode": "si",
            "display_app_base_url": "http://ha.test:8123",
        },
    )
    manager = DisplayAppManager(hass, entry, player, AsyncMock())
    manager.web.async_get_si_settings.return_value = ORIGINAL.copy()
    manager.web.async_foreground_app.return_value = HDMI
    hass.data["lg_rs232_ip"] = {"test": {"display_app": manager}}
    await manager.async_start()
    yield manager
    await manager.async_close()
    await hass.async_stop(force=True)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8123",
        "http://127.0.0.1:8123",
        "http://[::1]",
        "http://0.0.0.0",
        "http://224.0.0.1",
        "http://user:pass@ha.test",
        "http://ha.test/path",
        "http://ha.test/?secret=yes",
        "http://ha.test/#fragment",
        "file:///tmp/test",
    ],
)
def test_panel_url_rejects_unusable_or_secret_urls(url):
    with pytest.raises(ValueError):
        validate_base_url(url)


def test_valid_panel_base_url():
    assert validate_base_url("https://ha.test:8123/") == "https://ha.test:8123"


async def test_url_uses_auto_ha_network_address(app):
    app.entry.options.pop("display_app_base_url")
    with patch(
        "custom_components.lg_rs232_ip.display_app.get_url",
        return_value="http://ha.test:8123",
    ):
        assert app.url().startswith("http://ha.test:8123/api/")
    with patch(
        "custom_components.lg_rs232_ip.display_app.get_url",
        return_value="http://localhost:8123",
    ):
        with pytest.raises(HomeAssistantError, match="LG-accessible"):
            app.url()


async def test_token_persists_and_never_enters_diagnostics(app):
    second = DisplayAppManager(app.hass, app.entry, app.controller, app.web)
    await second.async_start()
    assert second.token == app.token and len(app.token) >= 40
    assert app.token not in json.dumps(app.attributes)
    assert "ha.test" not in json.dumps(app.attributes)


async def test_selected_sensors_only_while_presenting_and_ack_starts_duration(app):
    app.entry.options["display_app_entities"] = [
        "sensor.temperature",
        "sensor.unknown",
        "light.private",
    ]
    app.hass.states.async_set(
        "sensor.temperature",
        "21",
        {"friendly_name": "Room", "unit_of_measurement": "°C", "secret": "not shared"},
    )
    app.hass.states.async_set("light.private", "on")
    assert app.state()["content"] is None
    with patch(
        "custom_components.lg_rs232_ip.display_app.time.monotonic", return_value=100
    ):
        identifier = app.begin("<script>", "Test", 20, True)
        app.event({"type": "rendered", "id": identifier})
        await app.wait_rendered(identifier)
        state = app.state()
    assert state["content"]["cards"] == [{"name": "Room", "value": "21", "unit": "°C"}]
    assert state["content"]["title"] == "<script>"
    with patch(
        "custom_components.lg_rs232_ip.display_app.time.monotonic", return_value=121
    ):
        assert app.state()["content"] is None
    app.end(identifier)
    assert app.state()["content"] is None


async def test_old_ack_does_not_complete_new_presentation(app):
    identifier = app.begin("Test", "", 1)
    app.event({"type": "rendered", "id": "stale"})
    assert not app._rendered.is_set()
    app.end(identifier)
    with pytest.raises(HomeAssistantError, match="cancelled"):
        await app.wait_rendered(identifier)


async def test_api_is_per_entry_and_token_bound_and_revoked_when_disabled(app):
    http = web.Application()
    view = DisplayAppView(app.hass)
    view.register(app.hass, http, http.router)
    base = f"/api/lg_rs232_ip/display_app/test/{app.token}"
    async with TestClient(TestServer(http)) as client:
        for path in [
            base.replace(app.token, "wrong"),
            base.replace("/test/", "/other/"),
        ]:
            assert (await client.get(path + "/index.html")).status == 404
        response = await client.get(base + "/index.html")
        assert response.status == 200
        assert response.headers["Cache-Control"] == "no-store"
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
        assert (await client.get(base + "/unknown")).status == 404
        assert (await (await client.get(base + "/state")).json())["content"] is None
        assert (
            await client.post(
                base + "/event", json={"type": "execute", "command": "anything"}
            )
        ).status == 400
        assert (await client.post(base + "/event", data="x" * 4097)).status == 413

        async def fragments():
            yield b'{"type":'
            await asyncio.sleep(0.01)
            yield b'"hello","version":"1.0.0","bridge":true}'

        assert (await client.post(base + "/event", data=fragments())).status == 200
        assert app.client_has_bridge
        app.enabled = False
        assert (await client.get(base + "/state")).status == 404


async def test_si_original_saved_before_write_and_restored(app):
    async def write(settings):
        saved = await app.store.async_load()
        assert saved["previous"] == ORIGINAL
        app.web.async_get_si_settings.return_value = settings

    app.web.async_set_si_settings.side_effect = write
    await app.async_prepare_si(HDMI, True)
    assert app.saved["installed"]["fqdnAddr"] == app.url()
    await app.async_recover_si()
    assert app.saved == {"token": app.token}
    assert app.web.async_get_si_settings.return_value == ORIGINAL


async def test_si_restart_recovers_owned_app_and_configuration(app):
    await app.async_prepare_si(HDMI, True)
    app.web.async_get_si_settings.return_value = app.saved["installed"]
    app.web.async_foreground_app.return_value = SI_APP_ID
    second = DisplayAppManager(app.hass, app.entry, app.controller, app.web)
    await second.async_start()
    await second.async_restore_si()
    app.web.async_launch_app.assert_awaited_once_with(HDMI)
    app.web.async_set_si_settings.assert_awaited_with(ORIGINAL)
    assert "previous" not in second.saved


async def test_si_existing_or_externally_changed_app_is_not_overwritten(app):
    app.web.async_get_si_settings.return_value = {**ORIGINAL, "appLaunchMode": "local"}
    with pytest.raises(HomeAssistantError, match="existing SI"):
        await app.async_prepare_si(HDMI, True)
    app.web.async_set_si_settings.assert_not_awaited()
    app.web.async_get_si_settings.return_value = ORIGINAL
    await app.async_prepare_si(HDMI, True)
    app.web.async_get_si_settings.return_value = {
        **ORIGINAL,
        "fqdnAddr": "https://someone.test",
    }
    with pytest.raises(HomeAssistantError, match="changed outside"):
        await app.async_restore_si()
    assert "previous" in app.saved
    app.web.async_launch_app.assert_not_awaited()


async def test_si_failed_ack_preserves_recovery_journal(app):
    app.web.async_set_si_settings.side_effect = LGWebError("failure")
    with pytest.raises(HomeAssistantError, match="not confirmed"):
        await app.async_prepare_si(HDMI, True)
    assert app.saved["attempted"]["fqdnAddr"] == app.url()
    assert (await app.store.async_load())["previous"] == ORIGINAL


async def test_si_recovery_does_not_wake_or_interrupt_external_owner(app):
    await app.async_prepare_si(HDMI, True)
    app.controller._lg_display.async_get_power_status.return_value = False
    with pytest.raises(HomeAssistantError, match="awake"):
        await app.async_restore_si()
    app.controller._lg_display.async_power_on.assert_not_awaited()
    app.controller.external_owner = "av"
    with pytest.raises(HomeAssistantError, match="Stop"):
        await app.async_restore_si()


async def test_web_si_read_validate_write_and_no_mutation_replay():
    manager = LGWebManager("display.test", "secret", "ab" * 32)
    manager._api = AsyncMock(return_value=ORIGINAL)
    assert await manager.async_get_si_settings() == ORIGINAL
    manager._api.side_effect = [{"returnValue": True}, ORIGINAL]
    await manager.async_set_si_settings(ORIGINAL)
    manager._api.reset_mock()
    manager._api.side_effect = LGWebError("bad ack")
    with pytest.raises(LGWebError):
        await manager.async_set_si_settings(ORIGINAL)
    manager._api.assert_awaited_once()
    for invalid in [
        {},
        {**ORIGINAL, "appType": "unknown"},
        {**ORIGINAL, "serverIpPort": "-1"},
    ]:
        with pytest.raises(LGWebError):
            manager.validate_si_settings(invalid)
    with pytest.raises(LGWebError, match="Unsupported"):
        await manager.async_launch_app("arbitrary.application")


@pytest.fixture
def si_presentation(player):
    manager = Mock(mode="si")
    manager.begin.return_value = "presentation"
    manager.content = {}
    manager.async_prepare_si = AsyncMock()
    manager.async_recover_si = AsyncMock()
    manager.async_owns_si = AsyncMock(return_value=True)
    manager.wait_rendered = AsyncMock()
    web_manager = AsyncMock()
    web_manager.async_foreground_app.side_effect = [HDMI, HDMI, SI_APP_ID, HDMI]
    player.hass.data["lg_rs232_ip"]["test"].update(
        display_app=manager, web_manager=web_manager
    )
    return player, manager, web_manager


APP_REQUEST = dict(
    kind="display_app",
    title="Test",
    message="Hi",
    duration=0,
    priority="normal",
    dashboard=True,
    layout="fullscreen",
)


async def test_si_presentation_confirms_render_and_restores_hdmi_and_settings(
    si_presentation,
):
    player, manager, web_manager = si_presentation
    await player._async_present_native(APP_REQUEST)
    assert [call.args[0] for call in web_manager.async_launch_app.await_args_list] == [
        SI_APP_ID,
        HDMI,
    ]
    manager.wait_rendered.assert_awaited_once_with("presentation")
    manager.async_recover_si.assert_awaited_once()
    manager.end.assert_called_once_with("presentation")
    assert manager.content["hdmi"] == "ext://hdmi:1"
    player._lg_display.async_set_input.assert_not_awaited()
    assert player._presentation_error is None


async def test_si_failed_render_still_restores_and_clears_content(si_presentation):
    player, manager, web_manager = si_presentation
    manager.wait_rendered.side_effect = HomeAssistantError("No callback")
    with pytest.raises(HomeAssistantError, match="callback"):
        await player._async_present_native(APP_REQUEST)
    web_manager.async_launch_app.assert_awaited_with(HDMI)
    manager.async_recover_si.assert_awaited_once()
    manager.end.assert_called_once()


async def test_si_physical_input_change_is_not_overridden(si_presentation):
    player, manager, web_manager = si_presentation
    web_manager.async_foreground_app.side_effect = [HDMI, HDMI, "com.webos.app.hdmi2"]
    await player._async_present_native(APP_REQUEST)
    web_manager.async_launch_app.assert_awaited_once_with(SI_APP_ID)
    manager.async_recover_si.assert_awaited_once()


async def test_si_cancellation_during_setting_keeps_recovery(si_presentation):
    player, manager, web_manager = si_presentation
    started, finish = asyncio.Event(), asyncio.Event()

    async def prepare(*_):
        started.set()
        await finish.wait()

    manager.async_prepare_si.side_effect = prepare
    task = asyncio.create_task(player._async_present_native(APP_REQUEST))
    await started.wait()
    task.cancel()
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    web_manager.async_launch_app.assert_not_awaited()
    manager.async_recover_si.assert_awaited_once()
    manager.end.assert_called_once()


async def test_si_cancellation_after_start_restores_input(si_presentation):
    player, manager, web_manager = si_presentation
    started = asyncio.Event()

    async def wait(*_):
        started.set()
        await asyncio.Event().wait()

    manager.wait_rendered.side_effect = wait
    task = asyncio.create_task(player._async_present_native(APP_REQUEST))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    web_manager.async_launch_app.assert_awaited_with(HDMI)
    manager.async_recover_si.assert_awaited_once()


async def test_website_mode_rejects_hdmi_layouts(app):
    app.mode = "website"
    with pytest.raises(HomeAssistantError, match="require SI"):
        app.begin("Test", "", 10, layout="pip")
    assert app.content is None


@pytest.mark.parametrize("initial_osd", [False, True])
async def test_si_switches_use_real_osd_guard_and_preserve_manual_off(
    si_presentation, initial_osd
):
    from custom_components.lg_rs232_ip.lg_display import LGDisplay

    player, manager, web_manager = si_presentation
    display = LGDisplay("display.test")
    display.suppress_osd_during_switch = True
    display.async_get_power_status = AsyncMock(return_value=True)
    display.async_get_input = AsyncMock(return_value=0x90)
    osd = int(initial_osd)

    async def command(first, second, value, **kwargs):
        nonlocal osd
        assert (first, second) == ("k", "l")
        if value != 255:
            osd = value
        return osd

    display.async_send_command = AsyncMock(side_effect=command)
    player._lg_display = display
    with patch(
        "custom_components.lg_rs232_ip.lg_display.asyncio.sleep", new_callable=AsyncMock
    ):
        await player._async_present_native(APP_REQUEST)
    assert osd == int(initial_osd)
    writes = [
        call.args[2]
        for call in display.async_send_command.await_args_list
        if call.args[2] != 255
    ]
    assert writes == ([0, 1, 0, 1] if initial_osd else [])


async def test_si_pending_restore_retries_when_awake_without_taking_active_screen(app):
    await app.async_prepare_si(HDMI, True)
    app.web.async_get_si_settings.return_value = app.saved["installed"]
    app.controller._presentation_active = True
    await app.async_maybe_recover()
    assert "previous" in app.saved
    app.controller._presentation_active = False
    await app.async_maybe_recover()
    assert "previous" not in app.saved


async def test_successful_si_cleanup_does_not_erase_render_failure(app):
    await app.async_prepare_si(HDMI, True)
    app.web.async_get_si_settings.return_value = app.saved["installed"]
    app.last_error = "render_timeout"
    await app.async_recover_si()
    assert app.last_error == "render_timeout"
    assert app.status == "error"


async def test_display_app_website_fallback_restores_url_and_hdmi(si_presentation):
    player, manager, web_manager = si_presentation
    manager.mode = "website"
    manager.url.return_value = "http://ha.test/app"
    web_manager.validate_url = lambda value: value
    previous = {"playViaUrlMode": "off", "playViaUrl": ""}
    temporary = {"playViaUrlMode": "on", "playViaUrl": manager.url()}
    web_manager.async_get_url_settings.side_effect = [previous, temporary, temporary]
    web_manager.async_foreground_app.side_effect = [
        HDMI,
        HDMI,
        "com.webos.app.browser",
        "com.webos.app.browser",
        HDMI,
    ]
    await player._async_present_native(APP_REQUEST)
    assert [
        call.args[0] for call in web_manager.async_set_url_settings.await_args_list
    ] == [temporary, previous]
    assert [
        call.args[0] for call in player._lg_display.async_set_input.await_args_list
    ] == [0xE3, 0x90]
    manager.async_prepare_si.assert_not_awaited()
    manager.wait_rendered.assert_awaited_once()
    manager.end.assert_called_once()
