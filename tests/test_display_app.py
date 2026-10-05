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


def connect_app(app):
    from custom_components.lg_rs232_ip.display_app import APP_VERSION

    app.event(
        {
            "type": "hello",
            "version": APP_VERSION,
            "bridge": True,
            "visible": True,
            "hdmi_ready": True,
            "capture": True,
        }
    )


async def resident_app(app):
    app.resident = True

    async def write(settings):
        app.web.async_get_si_settings.return_value = settings

    async def launch(identifier):
        app.web.async_foreground_app.return_value = identifier

    app.web.async_set_si_settings.side_effect = write
    app.web.async_launch_app.side_effect = launch
    await app.async_maintain_resident()
    connect_app(app)
    return app


async def test_resident_idle_autostarts_once_and_never_blocks_standby(app):
    await resident_app(app)
    assert app.resident_connected and app.logical_input == 0x90
    assert app.state()["idle_hdmi"] == "ext://hdmi:1"
    assert not app.controller.presentation_active
    await app.async_maintain_resident()
    app.web.async_launch_app.assert_awaited_once_with(SI_APP_ID)
    app.controller._lg_display.async_get_power_status.return_value = False
    await app.async_maintain_resident()
    assert not app.connected and app.logical_input is None
    app.controller._lg_display.async_power_on.assert_not_awaited()
    app.controller._lg_display.async_get_power_status.return_value = True
    app.web.async_foreground_app.return_value = HDMI
    await app.async_maintain_resident()
    assert app.web.async_launch_app.await_count == 2


async def test_resident_physical_input_change_pauses_until_resume(app):
    await resident_app(app)
    app.web.async_foreground_app.return_value = "com.webos.app.hdmi2"
    await app.async_maintain_resident()
    assert app.saved["paused"] and not app.resident_connected
    await app.async_maintain_resident()
    assert app.web.async_launch_app.await_count == 1
    # Explicit resume adopts the selected physical HDMI inside the app.
    app.controller._lg_display.async_get_input.return_value = 0x91
    await app.async_resume()
    assert app.selected_input == 0x91
    assert not app.saved.get("paused")
    assert app.web.async_launch_app.await_count == 2


async def test_resident_lost_heartbeat_keeps_hdmi_and_recovers_without_switch(app):
    await resident_app(app)
    app.last_seen = 0
    app._resident_started -= 31
    for _ in range(3):
        await app.async_maintain_resident()
    assert app.web.async_foreground_app.return_value == SI_APP_ID
    assert app.last_error == "resident_connection_lost"
    assert not app.saved.get("paused")
    app.web.async_launch_app.assert_awaited_once()
    connect_app(app)
    await app.async_maintain_resident()
    assert app.resident_connected and app.last_error is None


async def test_connected_resident_presentation_has_no_launch_input_or_si_write(app):
    await resident_app(app)
    app.web.reset_mock()

    async def rendered(identifier):
        app.event({"type": "rendered", "id": identifier})

    app.wait_rendered = AsyncMock(side_effect=rendered)
    assert await app.async_present_connected(APP_REQUEST)
    assert not app.controller.presentation_active and app.content is None
    assert app.state()["idle_hdmi"] == "ext://hdmi:1"
    app.web.async_launch_app.assert_not_awaited()
    app.web.async_get_si_settings.assert_not_awaited()
    app.web.async_foreground_app.assert_not_awaited()
    app.web.async_set_si_settings.assert_not_awaited()
    app.controller._lg_display.async_set_input.assert_not_awaited()


async def test_resident_disable_restores_owned_si_and_hdmi(app):
    await resident_app(app)
    app.resident = False
    app.enabled = False
    await app.async_restore_si()
    assert app.web.async_foreground_app.return_value == HDMI
    assert app.web.async_get_si_settings.return_value == ORIGINAL
    assert "previous" not in app.saved
    assert not app.connected


async def test_capture_requires_active_current_client_and_rejects_stale_frame(app):
    assert await app.async_capture(720) is None
    connect_app(app)
    task = asyncio.create_task(app.async_capture(720))
    await asyncio.sleep(0)
    ticket = app.state()["capture"]
    assert ticket["height"] == 720
    with pytest.raises(ValueError):
        app.accept_frame("old-request", b"\xff\xd8\xffjpeg\xff\xd9")
    with pytest.raises(ValueError):
        app.accept_frame(ticket["id"], b"not-an-image")
    assert await app.async_capture(720) is None  # bounded to one outstanding request
    app.accept_frame(ticket["id"], b"\xff\xd8\xffjpeg\xff\xd9")
    assert await task == b"\xff\xd8\xffjpeg\xff\xd9"
    assert app.state()["capture"] is None
    app.event({"type": "heartbeat", "visible": False})
    assert await app.async_capture(720) is None


async def test_capture_failure_backoff_and_close_release_waiter(app):
    connect_app(app)
    task = asyncio.create_task(app.async_capture(720))
    await asyncio.sleep(0)
    app.event({"type": "capture_error", "id": app._capture["id"]})
    assert await task is None
    assert await app.async_capture(720) is None
    app._capture_retry = 0
    task = asyncio.create_task(app.async_capture(720))
    await asyncio.sleep(0)
    await app.async_close()
    assert await task is None


async def test_camera_request_wakes_waiting_app_poll_and_frame_route_is_scoped(app):
    connect_app(app)
    http = web.Application()
    view = DisplayAppView(app.hass)
    view.register(app.hass, http, http.router)
    base = f"/api/lg_rs232_ip/display_app/test/{app.token}"
    async with TestClient(TestServer(http)) as client:
        assert (
            await client.post(base + "/frame?id=unsolicited", data=b"jpeg")
        ).status == 409
        poll = asyncio.create_task(app.async_state(str(app._revision)))
        await asyncio.sleep(0)
        capture = asyncio.create_task(app.async_capture(720))
        ticket = (await asyncio.wait_for(poll, 1))["capture"]
        wrong = base.replace(app.token, "wrong")
        assert (
            await client.post(wrong + "/frame?id=" + ticket["id"], data=b"jpeg")
        ).status == 404
        response = await client.post(
            base + "/frame?id=" + ticket["id"], data=b"\xff\xd8\xffjpeg\xff\xd9"
        )
        assert response.status == 200
        assert await capture == b"\xff\xd8\xffjpeg\xff\xd9"


async def test_dynamic_toast_uses_app_when_connected_and_native_on_disconnect(app):
    await resident_app(app)
    player = app.controller
    player.hass.data["lg_rs232_ip"]["test"].update(display_app=app, web_manager=app.web)
    player._enqueue_presentation = AsyncMock()
    await player.async_show_toast("hello")
    request = player._enqueue_presentation.await_args.args[0]
    assert request["toast_fallback"] and request["layout"] == "overlay"
    app.last_seen = 0
    await player._async_present_native(request)
    app.web.async_toast.assert_awaited_once_with("hello")


async def test_resident_wake_grace_and_transient_web_failure_recover(app):
    await resident_app(app)
    app.controller._lg_display.async_get_power_status.return_value = False
    await app.async_maintain_resident()
    assert app._resident_started == 0
    app.controller._lg_display.async_get_power_status.return_value = True
    app.web.async_foreground_app.side_effect = LGWebError("booting")
    await app.async_maintain_resident()
    assert app.last_error == "resident_start_failed"
    app.web.async_foreground_app.side_effect = None
    app.web.async_foreground_app.return_value = SI_APP_ID
    connect_app(app)
    await app.async_maintain_resident()
    assert app.resident_connected and app.last_error is None
    assert not app.saved.get("paused")


async def test_controller_close_cancels_resident_message_without_late_refresh(app):
    await resident_app(app)
    controller = app.controller
    controller.hass.data["lg_rs232_ip"]["test"].update(
        display_app=app, web_manager=app.web
    )
    waiting = asyncio.Event()

    async def wait(_):
        waiting.set()
        await asyncio.Event().wait()

    app.wait_rendered = wait
    await controller._enqueue_presentation(APP_REQUEST)
    await waiting.wait()
    await controller.async_close()
    assert controller._ha_stopping and not controller.presentation_active
    assert app.content is None
    assert app.web.async_launch_app.await_count == 1


async def test_resident_unknown_input_is_not_provisioned(app):
    app.controller._lg_display.async_get_input.return_value = None
    with pytest.raises(HomeAssistantError, match="preserve input"):
        await app.async_prepare_si(HDMI, True, resident=True)
    app.web.async_set_si_settings.assert_not_awaited()
    assert "previous" not in app.saved


async def test_av_adapter_resident_idle_does_not_block_power_and_matching_input(app):
    from custom_components.lg_rs232_ip.api import get_display_api

    await resident_app(app)
    controller = app.controller
    controller.hass.data["lg_rs232_ip"]["test"].update(
        display_app=app, controller=controller
    )
    api = get_display_api(controller.hass, "test")
    assert await api.async_get_input(use_cache=False) == 0x90
    assert await api.async_set_input(0x90)
    controller._lg_display.async_set_input.assert_not_awaited()
    assert not api.presentation_active
    assert await api.async_power_off()
    controller._lg_display.async_power_off.assert_awaited_once()


async def test_av_lease_temporarily_leaves_resident_and_resumes(app):
    from custom_components.lg_rs232_ip.api import get_display_api

    await resident_app(app)
    controller = app.controller
    controller.hass.data["lg_rs232_ip"]["test"].update(
        display_app=app, controller=controller
    )
    api = get_display_api(controller.hass, "test")
    token = await api.async_begin_external_presentation()
    assert app.saved["paused"] and app.web.async_foreground_app.return_value == HDMI
    await api.async_end_external_presentation("wrong")
    assert controller.external_owner == token
    await api.async_end_external_presentation(token)
    assert controller.external_owner is None
    assert app.web.async_foreground_app.return_value == SI_APP_ID


@pytest.mark.parametrize("osd", [False, True])
async def test_resident_start_and_pause_use_real_osd_guard(app, osd):
    from custom_components.lg_rs232_ip.lg_display import LGDisplay

    display = LGDisplay("display.test")
    display.suppress_osd_during_switch = True
    display.async_get_power_status = AsyncMock(return_value=True)
    display.async_get_input = AsyncMock(return_value=0x90)
    value = int(osd)

    async def command(first, second, setting, **kwargs):
        nonlocal value
        assert (first, second) == ("k", "l")
        if setting != 255:
            value = setting
        return value

    display.async_send_command = AsyncMock(side_effect=command)
    app.controller._lg_display = display
    with patch(
        "custom_components.lg_rs232_ip.lg_display.asyncio.sleep", new_callable=AsyncMock
    ):
        await resident_app(app)
        await app.async_pause_resident()
    writes = [
        c.args[2]
        for c in display.async_send_command.await_args_list
        if c.args[2] != 255
    ]
    assert value == int(osd)
    assert writes == ([0, 1, 0, 1] if osd else [])


async def test_real_ha_stop_listener_is_not_removed_twice(player, tmp_path, caplog):
    from homeassistant.const import EVENT_HOMEASSISTANT_STOP

    hass = HomeAssistant(str(tmp_path))
    player.hass = hass
    hass.data["lg_rs232_ip"] = {"test": {"controller": player}}
    player.async_refresh = AsyncMock()
    await player.async_start()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert player._ha_stopping and player._stop_unsub is None
    await player.async_close()
    await hass.async_stop(force=True)
    assert "unknown job listener" not in caplog.text


async def test_native_media_failure_does_not_leave_resident_permanently_paused(app):
    await resident_app(app)
    player = app.controller
    player.hass.data["lg_rs232_ip"]["test"].update(display_app=app, web_manager=app.web)
    player._async_download_native_image = AsyncMock(
        side_effect=HomeAssistantError("download failed")
    )
    with pytest.raises(HomeAssistantError, match="download failed"):
        await player._async_present_native(
            dict(
                kind="native_image",
                media_id="http://test/image",
                duration=1,
                priority="normal",
            )
        )
    assert not app.saved.get("paused")
    assert app.web.async_foreground_app.return_value == HDMI
    await app.async_maintain_resident()
    assert app.web.async_foreground_app.return_value == SI_APP_ID


async def test_missing_hdmi_signal_does_not_disconnect_or_relaunch_app(app):
    await resident_app(app)
    app.event({"type": "heartbeat", "visible": True, "hdmi_ready": False})
    app._resident_started -= 300
    await app.async_maintain_resident()
    assert app.resident_connected and app.logical_input == 0x90
    assert not app.attributes["hdmi_signal_ready"]
    app.web.async_launch_app.assert_awaited_once()


@pytest.mark.parametrize("via_api", [False, True])
async def test_hdmi_selection_uses_app_ack_preserves_original_and_osd_guard(
    app, via_api
):
    from custom_components.lg_rs232_ip.api import get_display_api

    await resident_app(app)
    controller = app.controller
    controller.hass.data["lg_rs232_ip"]["test"].update(
        display_app=app, controller=controller
    )
    controller._lg_display.async_suppress_osd_for_switch.reset_mock()
    app.web.reset_mock()
    operation = (
        get_display_api(controller.hass, "test").async_set_input
        if via_api
        else controller.async_select_input
    )
    task = asyncio.create_task(operation(0x91))
    async with asyncio.timeout(1):
        while not app._input_request:
            await asyncio.sleep(0)
    assert app.state()["idle_hdmi"] == "ext://hdmi:2"
    app.event({"type": "input_applied", "id": "stale"})
    assert not task.done()
    app.event({"type": "input_applied", "id": app._input_request})
    await task
    assert app.saved["original_input"] == 0x90 and app.logical_input == 0x91
    assert controller._source == "HDMI 2"
    assert not app.saved.get("paused")
    assert controller._lg_display.async_suppress_osd_for_switch.call_count == 1
    controller._lg_display.async_set_input.assert_not_awaited()
    app.web.async_launch_app.assert_not_awaited()
    app.web.async_set_si_settings.assert_not_awaited()
    await operation(0x91)  # idempotent; no second guard or source reload
    assert controller._lg_display.async_suppress_osd_for_switch.call_count == 1


async def test_cancelled_hdmi_selection_finishes_owned_transaction(app):
    await resident_app(app)
    task = asyncio.create_task(app.async_select_hdmi(0x91))
    async with asyncio.timeout(1):
        while not app._input_request:
            await asyncio.sleep(0)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    app.event({"type": "input_applied", "id": app._input_request})
    with pytest.raises(asyncio.CancelledError):
        await task
    assert app.selected_input == 0x91 and app._input_request is None
    assert (await app.store.async_load())["selected_input"] == 0x91
    app.controller._lg_display.async_set_input.assert_not_awaited()


async def wait_content(app, title):
    async with asyncio.timeout(1):
        while not app.content or app.content["title"] != title:
            await asyncio.sleep(0)


async def test_resident_burst_replaces_visible_and_pending_messages_without_refresh(
    app,
):
    await resident_app(app)
    player = app.controller
    player.hass.data["lg_rs232_ip"]["test"].update(display_app=app, web_manager=app.web)
    player.async_refresh = AsyncMock()
    app.web.reset_mock()
    await player._enqueue_presentation(dict(APP_REQUEST, title="first", duration=60))
    await wait_content(app, "first")
    old_id = app.content["id"]
    # Even an unacknowledged request must be replaceable immediately.
    for n in range(20):
        await player._enqueue_presentation(dict(APP_REQUEST, title=str(n), duration=60))
    assert len(player._presentation_queue) == 1
    await wait_content(app, "19")
    app.event({"type": "rendered", "id": old_id})
    assert not app.content.get("rendered")
    app.event({"type": "rendered", "id": app.content["id"]})
    await player.async_clear_content()
    assert app.content is None and not player.presentation_active
    player.async_refresh.assert_not_awaited()
    app.web.async_launch_app.assert_not_awaited()
    app.web.async_foreground_app.assert_not_awaited()
    app.web.async_get_si_settings.assert_not_awaited()


async def test_urgent_resident_message_retains_priority_with_only_latest_normal_waiting(
    app,
):
    await resident_app(app)
    player = app.controller
    player.hass.data["lg_rs232_ip"]["test"].update(display_app=app, web_manager=app.web)
    await player._enqueue_presentation(
        dict(APP_REQUEST, title="urgent", priority="urgent", duration=60)
    )
    await wait_content(app, "urgent")
    for n in range(20):
        await player._enqueue_presentation(dict(APP_REQUEST, title=str(n), duration=60))
    assert len(player._presentation_queue) == 1
    assert not player._resident_replace.is_set()
    await player._enqueue_presentation(
        dict(APP_REQUEST, title="new urgent", priority="urgent", duration=60)
    )
    await wait_content(app, "new urgent")
    assert not player._presentation_queue
    await player.async_clear_content()


async def test_disconnected_resident_request_does_not_launch_temporary_app(app):
    await resident_app(app)
    app.last_seen = 0
    player = app.controller
    player.hass.data["lg_rs232_ip"]["test"].update(display_app=app, web_manager=app.web)
    app.web.reset_mock()
    with pytest.raises(HomeAssistantError, match="not connected"):
        await player._async_present_native(APP_REQUEST)
    app.web.async_launch_app.assert_not_awaited()
    app.web.async_set_si_settings.assert_not_awaited()


async def test_idle_long_poll_waits_without_periodic_updates_and_close_releases_it(app):
    poll = asyncio.create_task(app.async_state(str(app._revision)))
    await asyncio.sleep(0)
    connect_app(app)
    assert not poll.done()  # Heartbeats must not wake the content channel.
    await app.async_close()
    assert (await asyncio.wait_for(poll, 1))["content"] is None


async def test_external_si_change_disables_fast_path_without_overwriting_settings(app):
    await resident_app(app)
    app.web.async_get_si_settings.return_value = dict(
        ORIGINAL, fqdnAddr="http://other.test"
    )
    await app.async_maintain_resident()
    assert not app.resident_connected
    app.web.async_launch_app.assert_awaited_once()
    assert app.web.async_set_si_settings.await_count == 1


@pytest.mark.parametrize("osd", [False, True])
async def test_in_app_hdmi_selection_preserves_manual_osd_state(app, osd):
    from custom_components.lg_rs232_ip.lg_display import LGDisplay

    await resident_app(app)
    display = LGDisplay("display.test")
    display.suppress_osd_during_switch = True
    value = int(osd)

    async def command(first, second, setting, **kwargs):
        nonlocal value
        assert (first, second) == ("k", "l")
        if setting != 255:
            value = setting
        return value

    display.async_send_command = AsyncMock(side_effect=command)
    app.controller._lg_display = display
    changed = app.changed

    def acknowledge():
        changed()
        if app._input_request:
            assert value == 0
            app.event({"type": "input_applied", "id": app._input_request})

    app.changed = acknowledge
    with patch(
        "custom_components.lg_rs232_ip.lg_display.asyncio.sleep", new_callable=AsyncMock
    ):
        assert await app.async_select_hdmi(0x91)
    assert value == int(osd)
    assert [
        c.args[2]
        for c in display.async_send_command.await_args_list
        if c.args[2] != 255
    ] == ([0, 1] if osd else [])


async def test_allowed_sensor_changes_wake_dashboard_only(app):
    app.entry.options["display_app_entities"] = ["sensor.temperature"]
    await app.async_start()
    initial = app._revision
    app.hass.states.async_set("sensor.temperature", "21")
    await app.hass.async_block_till_done()
    assert app._revision == initial
    app.begin("Test", "", 60, dashboard=True)
    initial = app._revision
    app.hass.states.async_set("sensor.not_allowed", "12")
    await app.hass.async_block_till_done()
    assert app._revision == initial
    app.hass.states.async_set("sensor.temperature", "22")
    await app.hass.async_block_till_done()
    assert app._revision == initial + 1
    assert app.state()["content"]["cards"][0]["value"] == "22"


async def test_hdmi_timeout_rolls_back_before_restoring_osd(app):
    from contextlib import asynccontextmanager

    await resident_app(app)
    restored = False

    @asynccontextmanager
    async def guard():
        nonlocal restored
        try:
            yield
        finally:
            assert app.selected_input == 0x90
            assert app.state()["idle_hdmi"] == "ext://hdmi:1"
            assert app._input_request is None
            restored = True

    async def timeout(awaitable, seconds):
        awaitable.close()
        raise TimeoutError

    app.controller._lg_display.async_suppress_osd_for_switch = guard
    with patch(
        "custom_components.lg_rs232_ip.resident_app.asyncio.wait_for",
        side_effect=timeout,
    ):
        with pytest.raises(HomeAssistantError, match="confirm HDMI"):
            await app.async_select_hdmi(0x91)
    assert restored
    app.controller._lg_display.async_set_input.assert_not_awaited()


async def test_layout_heartbeat_reports_only_supported_scene_and_revision(app):
    from custom_components.lg_rs232_ip.display_app import APP_VERSION

    app.event(
        {
            "type": "hello",
            "version": APP_VERSION,
            "visible": True,
            "layout_scene": "signal",
            "layout_revision": 7,
        }
    )
    assert app.attributes["layout_scene"] == "signal"
    assert app.attributes["layout_revision"] == 7
    app.event(
        {"type": "heartbeat", "layout_scene": "invalid", "layout_revision": "secret"}
    )
    assert app.attributes["layout_scene"] is None
    assert app.attributes["layout_revision"] is None


async def configure_dashboard(app):
    from custom_components.lg_rs232_ip.layouts import DisplayLayouts

    await resident_app(app)
    manager = DisplayLayouts(app.hass, app.entry)
    await manager.async_start()
    config = manager.document()["config"]
    config["enabled"] = True
    await manager.async_save(config, 0)
    app.layouts = manager
    app.controller.hass = app.hass
    app.hass.data["lg_rs232_ip"]["test"]["controller"] = app.controller
    return manager


async def acknowledge_selection(app, operation):
    task = asyncio.create_task(operation)
    async with asyncio.timeout(1):
        while not app._input_request:
            await asyncio.sleep(0)
    app.event({"type": "input_applied", "id": app._input_request})
    await task


async def test_dashboard_source_is_persistent_excludes_av_standby_and_hdmi_selection_exits(
    app,
):
    from custom_components.lg_rs232_ip.api import get_display_api
    from custom_components.lg_rs232_ip.media_player import LGDisplayMediaPlayer

    layouts = await configure_dashboard(app)
    try:
        entity = LGDisplayMediaPlayer(
            app.controller, SimpleNamespace(entry_id="test", options={})
        )
        api = get_display_api(app.hass, "test")
        assert entity.source_list[-2:] == ["Dashboard", "PiP"]
        assert api.dashboard_available
        app.web.reset_mock()
        app.controller._lg_display.async_set_input.reset_mock()
        await acknowledge_selection(app, entity.async_select_source("Dashboard"))
        assert app.state()["dashboard"] and entity.source == "Dashboard"
        assert api.presentation_active and not app.controller.presentation_active
        assert (
            await api.async_get_input() is None
            and await api.async_get_signal_status() is None
        )
        assert (await app.store.async_load())["dashboard"] is True
        app.web.async_launch_app.assert_not_awaited()
        app.controller._lg_display.async_set_input.assert_not_awaited()
        # Choosing the same physical input must still leave the Dashboard source.
        await acknowledge_selection(app, api.async_set_input(0x90))
        assert not app.state()["dashboard"] and entity.source == "HDMI 1"
        assert not api.presentation_active and await api.async_get_input() == 0x90
        assert app.saved["original_input"] == 0x90
    finally:
        await layouts.async_close()


async def test_dashboard_selection_rolls_back_on_missing_ack_and_respects_external_owner(
    app,
):
    layouts = await configure_dashboard(app)

    async def timeout_without_waiting(awaitable, _timeout):
        awaitable.close()
        raise TimeoutError

    try:
        with patch(
            "custom_components.lg_rs232_ip.resident_app.asyncio.wait_for",
            timeout_without_waiting,
        ):
            with pytest.raises(HomeAssistantError, match="confirm"):
                await app.async_select_dashboard()
        assert not app.dashboard_selected and app.selected_input == 0x90
        app.controller.external_owner = "someone"
        with pytest.raises(HomeAssistantError, match="external"):
            await app.controller.async_select_dashboard()
        assert not app.dashboard_selected
    finally:
        await layouts.async_close()


async def test_confirmed_power_off_releases_dashboard_standby_protection(app):
    from custom_components.lg_rs232_ip.api import get_display_api

    layouts = await configure_dashboard(app)
    try:
        await acknowledge_selection(app, app.controller.async_select_dashboard())
        api = get_display_api(app.hass, "test")
        assert api.dashboard_active
        app.controller.power = False
        app.controller._lg_display.async_get_power_status.return_value = False
        await app.async_maintain_resident(power=False)
        assert not api.dashboard_active
        async with api.supply_guard() as allowed:
            assert allowed
        assert (
            app.saved["dashboard"] is True
        )  # Restore the user's chosen source on wake.
    finally:
        await layouts.async_close()


async def test_paired_background_access_is_limited_to_this_displays_saved_images(app):
    from tests.test_layout_backgrounds import png

    layouts = await configure_dashboard(app)
    try:
        image_id = await layouts.backgrounds.async_upload(png())
        http = web.Application()
        DisplayAppView(app.hass).register(app.hass, http, http.router)
        base = f"/api/lg_rs232_ip/display_app/test/{app.token}"
        async with TestClient(TestServer(http)) as client:
            path = base + "/background.jpg?id=" + image_id
            assert (await client.get(path)).status == 404
            config = layouts.document()["config"]
            config["scenes"]["dashboard"].update(background="image", image_id=image_id)
            await layouts.async_save(config, layouts.revision)
            response = await client.get(path)
            assert response.status == 200 and response.content_type == "image/jpeg"
            assert "img-src 'self'" in response.headers["Content-Security-Policy"]
            assert (await client.get(path.replace("/test/", "/other/"))).status == 404
            assert (await client.get(path.replace(app.token, "wrong"))).status == 404
            assert (await client.post(path, data=png())).status != 200
    finally:
        await layouts.async_close()


async def test_dashboard_source_does_not_hide_a_custom_hdmi_label(app):
    from custom_components.lg_rs232_ip.media_player import LGDisplayMediaPlayer

    layouts = await configure_dashboard(app)
    try:
        entity = LGDisplayMediaPlayer(
            app.controller,
            SimpleNamespace(entry_id="test", options={"input_name_hdmi1": "Dashboard"}),
        )
        assert entity.source_list == [
            "Dashboard",
            "HDMI 2",
            "HDMI 3",
            "Dashboard (App)",
            "PiP",
        ]
        await acknowledge_selection(app, entity.async_select_source("Dashboard (App)"))
        assert entity.source == "Dashboard (App)"
        await acknowledge_selection(app, entity.async_select_source("Dashboard"))
        assert not app.dashboard_selected
    finally:
        await layouts.async_close()


async def test_paired_media_artwork_only_exposes_selected_saved_players(app):
    from custom_components.lg_rs232_ip.layout_config import element
    from custom_components.lg_rs232_ip.layout_api import (
        LayoutMediaView,
        LayoutSuggestionsView,
    )
    from tests.test_layout_cards import cover

    layouts = await configure_dashboard(app)
    app.hass.data["lg_rs232_ip"]["test"]["layouts"] = layouts
    app.hass.states.async_set(
        "media_player.sonos",
        "playing",
        {"entity_picture": "/private", "media_title": "One"},
    )
    layouts.media._cache["media_player.sonos"] = (
        layouts.media.key("media_player.sonos"),
        cover(),
        0,
    )

    @web.middleware
    async def auth(request, handler):
        request["ha_authenticated"] = request.headers.get("X-Auth") == "yes"
        request["hass_user"] = SimpleNamespace(
            is_admin=request.headers.get("X-Admin") == "yes"
        )
        return await handler(request)

    http = web.Application(middlewares=[auth])
    DisplayAppView(app.hass).register(app.hass, http, http.router)
    LayoutMediaView(app.hass).register(app.hass, http, http.router)
    LayoutSuggestionsView(app.hass).register(app.hass, http, http.router)
    url = f"/api/lg_rs232_ip/display_app/test/{app.token}/cover.jpg?entity=media_player.sonos&v={layouts.media.key('media_player.sonos')}"
    try:
        async with TestClient(TestServer(http)) as client:
            editor = "/api/lg_rs232_ip/layout_media/test/media_player.sonos"
            assert (await client.get(editor)).status == 401
            assert (await client.get(editor, headers={"X-Auth": "yes"})).status == 403
            assert (
                await client.get(editor, headers={"X-Auth": "yes", "X-Admin": "yes"})
            ).status == 200
            for endpoint in (editor, "/api/lg_rs232_ip/layout_suggestions/test"):
                assert (
                    await client.post(
                        endpoint, headers={"X-Auth": "yes", "X-Admin": "yes"}
                    )
                ).status == 405
            suggestions = "/api/lg_rs232_ip/layout_suggestions/test"
            assert (await client.get(suggestions)).status == 401
            assert (
                await client.get(suggestions, headers={"X-Auth": "yes"})
            ).status == 403
            assert (await client.get(url)).status == 404
            cfg = layouts.document()["config"]
            item = element("media", 4, 4, 50, 30)
            item["entity_id"] = "media_player.sonos"
            cfg["scenes"]["dashboard"]["elements"] = [item]
            await layouts.async_save(cfg, layouts.revision)
            assert (await client.get(url)).status == 200
            assert (await client.get(url.replace(app.token, "wrong"))).status == 404
            cfg["scenes"]["dashboard"]["elements"] = []
            await layouts.async_save(cfg, layouts.revision)
            assert (await client.get(url)).status == 404
            # A background alone authorizes its player; disabling revokes it.
            background = cfg["scenes"]["dashboard"]
            background.update(
                media_background_enabled=True,
                media_background_entity="media_player.sonos",
            )
            await layouts.async_save(cfg, layouts.revision)
            assert (await client.get(url)).status == 200
            background["media_background_enabled"] = False
            await layouts.async_save(cfg, layouts.revision)
            assert (await client.get(url)).status == 404
    finally:
        await layouts.async_close()


async def test_pip_source_is_independent_persisted_and_same_hdmi_exits_it(app):
    from custom_components.lg_rs232_ip.api import get_display_api
    from custom_components.lg_rs232_ip.media_player import LGDisplayMediaPlayer

    layouts = await configure_dashboard(app)
    try:
        entity = LGDisplayMediaPlayer(
            app.controller, SimpleNamespace(entry_id="test", options={})
        )
        api = get_display_api(app.hass, "test")
        assert api.pip_available and "PiP" in entity.source_list
        await acknowledge_selection(app, entity.async_select_source("PiP"))
        assert (
            app.pip_selected and not app.dashboard_selected and entity.source == "PiP"
        )
        assert app.state()["pip"] and not app.state()["dashboard"]
        assert (await app.store.async_load())["pip"] is True
        assert api.presentation_active and api.pip_active
        assert await api.async_get_input() is None
        assert await api.async_get_signal_status() is None
        # A separate instance reads the selected source from the recovery journal.
        second = DisplayAppManager(app.hass, app.entry, app.controller, app.web)
        second.layouts = layouts
        second.resident = True
        await second.async_start()
        assert second.pip_selected and not second.dashboard_selected
        await second.async_close()
        # Selecting Dashboard leaves PiP, selecting the same HDMI leaves both.
        await acknowledge_selection(app, entity.async_select_source("Dashboard"))
        assert app.dashboard_selected and not app.pip_selected
        await acknowledge_selection(app, api.async_select_pip())
        await acknowledge_selection(app, api.async_set_input(0x90))
        assert not app.pip_selected and entity.source == "HDMI 1"
        assert not api.presentation_active
    finally:
        await layouts.async_close()


async def test_failed_view_change_restores_pip_and_explicit_power_off_releases_guard(
    app,
):
    from custom_components.lg_rs232_ip.api import get_display_api

    layouts = await configure_dashboard(app)

    async def timeout(awaitable, _timeout):
        awaitable.close()
        raise TimeoutError

    try:
        await acknowledge_selection(app, app.async_select_pip())
        with patch(
            "custom_components.lg_rs232_ip.resident_app.asyncio.wait_for", timeout
        ):
            with pytest.raises(HomeAssistantError, match="confirm"):
                await app.async_select_dashboard()
        assert app.pip_selected and not app.dashboard_selected
        assert (await app.store.async_load())["pip"] is True
        api = get_display_api(app.hass, "test")
        app.controller.power = False
        app.controller._lg_display.async_get_power_status.return_value = False
        assert not api.pip_active
        async with api.supply_guard() as allowed:
            assert allowed
        assert app.saved["pip"]  # Wake keeps the selected view.
    finally:
        await layouts.async_close()


async def test_pip_label_collision_does_not_hide_physical_hdmi(app):
    from custom_components.lg_rs232_ip.media_player import LGDisplayMediaPlayer

    layouts = await configure_dashboard(app)
    try:
        entity = LGDisplayMediaPlayer(
            app.controller,
            SimpleNamespace(entry_id="test", options={"input_name_hdmi1": "PiP"}),
        )
        assert entity.pip_source == "PiP (App)"
        assert "PiP" in entity.source_list and "PiP (App)" in entity.source_list
        await acknowledge_selection(app, entity.async_select_source("PiP (App)"))
        assert entity.source == "PiP (App)"
        await acknowledge_selection(app, entity.async_select_source("PiP"))
        assert not app.pip_selected
    finally:
        await layouts.async_close()


async def test_aspect_ratio_payload_tracks_native_setting_and_subscription_is_closed(
    app,
):
    display = app.controller._lg_display
    display.subscribe_aspect_ratio.assert_called_once()
    display.aspect_ratio = 2
    assert app.state()["hdmi_fit"] == "fill"
    display.aspect_ratio = 6
    assert app.state()["hdmi_fit"] == "contain"
    display.aspect_ratio = None
    assert app.state()["hdmi_fit"] == "contain"
    await app.async_close()
    display.subscribe_aspect_ratio.return_value.assert_called_once()
