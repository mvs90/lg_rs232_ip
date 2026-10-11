"""SI being active is not evidence that its embedded HDMI source has a signal."""

from types import SimpleNamespace
from unittest.mock import patch
import pytest
from test_display_app import app  # noqa: F401
from custom_components.lg_rs232_ip.display_app import APP_VERSION, SI_APP_ID
from custom_components.lg_rs232_ip.api import get_display_api
from custom_components.lg_rs232_ip.sensor import LGDisplayStatusSensor


def sample(app, **values):
    app.resident = True
    app.saved.update(
        resident=True, selected_input=0x90, selected_app="com.webos.app.hdmi1"
    )
    app._resident_foreground = SI_APP_ID
    app._input_request = "current-request"
    app.controller.hass = app.hass
    app.hass.data["lg_rs232_ip"]["test"]["controller"] = app.controller
    app.event(
        {
            "type": "hello",
            "version": APP_VERSION,
            "visible": True,
            "layout_scene": "signal",
            "hdmi_signal": False,
            "hdmi_source": "ext://hdmi:1",
            "hdmi_request": "current-request",
            **values,
        }
    )
    return get_display_api(app.hass, "test")


@pytest.mark.parametrize("signal", [True, False, None])
async def test_resident_signal_overrides_raw_si_status_for_api_controller_and_sensor(
    app, signal
):
    api = sample(app, hdmi_signal=signal)
    app.controller._lg_display.async_get_signal_status.return_value = True
    assert await api.async_get_signal_status() is signal
    assert await app.controller.async_get_signal_status() is signal
    sensor = LGDisplayStatusSensor(
        app.controller._lg_display,
        "LG",
        "test",
        "signal_status",
        "Input Signal",
        "sv",
        2,
        {0: "No signal", 1: "Signal present"},
        signal_reader=app.controller.async_get_signal_status,
    )
    await sensor.async_update()
    assert (
        sensor.native_value
        == {True: "Signal present", False: "No signal", None: None}[signal]
    )
    app.controller._lg_display.async_get_signal_status.assert_not_awaited()


@pytest.mark.parametrize(
    "values",
    [
        {"hdmi_source": "ext://hdmi:2"},
        {"hdmi_source": None},
        {"hdmi_request": "old-request"},
        {"hdmi_signal": "false"},
        {"visible": False},
        {"version": "old"},
    ],
)
async def test_wrong_input_request_invalid_sample_or_hidden_app_is_unknown(app, values):
    api = sample(app, **values)
    assert app.hdmi_signal is None
    assert await api.async_get_signal_status() is None
    app.controller._lg_display.async_get_signal_status.assert_not_awaited()


async def test_unrelated_events_cannot_keep_stale_hdmi_sample_alive(app):
    with patch(
        "custom_components.lg_rs232_ip.display_app.time.monotonic", return_value=1000
    ):
        api = sample(app)
    with patch(
        "custom_components.lg_rs232_ip.display_app.time.monotonic", return_value=1013
    ):
        app.event({"type": "input_applied", "id": "current-request"})
        assert app.connected
        assert await api.async_get_signal_status() is None


async def test_native_hdmi_uses_hardware_signal_after_app_is_paused(app):
    api = sample(app)
    app.saved["paused"] = True
    app.controller._lg_display.async_get_signal_status.return_value = True
    assert await api.async_get_signal_status() is True
    app.controller._lg_display.async_get_signal_status.assert_awaited_once()


async def test_pip_context_preserves_protection_and_lists_only_non_hdmi_targets(app):
    api = sample(app)
    app.layouts = SimpleNamespace(
        config={
            "enabled": True,
            "scenes": {
                "dashboard": {"elements": []},
                "pip_view": {"elements": [{"kind": "hdmi"}]},
                "custom": {"elements": [{"kind": "clock"}, {"kind": "hdmi"}]},
                "music": {"elements": [{"kind": "media"}]},
            },
        },
        source_views={
            "dashboard": "Dashboard",
            "pip_view": "Dashboard PiP",
            "custom": "Custom PiP",
            "music": "Music",
        },
    )
    assert api.hdmi_context == {
        "mode": "fullscreen",
        "input_id": 0x90,
        "signal": False,
        "view": None,
    }
    assert api.no_signal_views == {"dashboard": "Dashboard", "music": "Music"}
    for selected in ("pip_view", "custom"):
        app.saved["custom_view"] = selected
        assert api.presentation_active
        assert await api.async_get_input() is None
        assert await api.async_get_signal_status() is None
        assert api.hdmi_context == {
            "mode": "pip",
            "input_id": 0x90,
            "signal": False,
            "view": selected,
        }
    app.saved["custom_view"] = "dashboard"
    assert api.hdmi_context is None
    app.saved["custom_view"] = "pip_view"
    app.controller._presentation_active = True
    assert api.hdmi_context is None


async def test_temporary_view_and_external_owner_do_not_enable_pip_policy(app):
    api = sample(app)
    app.controller._view_lease = {"view": "pip_view"}
    assert api.hdmi_context is None
    app.controller._view_lease = None
    app.controller.external_owner = "test"
    assert api.hdmi_context is None


async def test_countdown_payload_is_ephemeral_and_does_not_take_presentation_ownership(
    app,
):
    with patch(
        "custom_components.lg_rs232_ip.display_app.time.monotonic", return_value=1000
    ):
        api = sample(app)
        api.set_standby_notice("Stop in {seconds}", 1015)
        assert app.state()["standby_notice"] == {
            "message": "Stop in {seconds}",
            "remaining": 15,
        }
        assert not api.presentation_active
        app.client_hdmi_signal = True
        assert app.state()["standby_notice"] is None
        app.client_hdmi_signal = False
        app.controller._view_lease = {}
        assert app.state()["standby_notice"] is None
        app.controller._view_lease = None
        api.set_standby_notice()
        assert app.state()["standby_notice"] is None
