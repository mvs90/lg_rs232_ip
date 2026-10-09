"""HA outage configuration and the paired bootstrap needed by the resident app."""

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import pytest

from test_display_app import app  # noqa: F401
from custom_components.lg_rs232_ip.config_flow import _display_options_form
from custom_components.lg_rs232_ip.display_app import APP_VERSION, DisplayAppView


@pytest.mark.parametrize("value", [0, 1, 30, 600])
def test_offline_timeout_option_accepts_bounded_seconds(value):
    schema, errors, values = _display_options_form({"display_app_offline_timeout": value}, {})
    assert not errors
    assert values["display_app_offline_timeout"] == value
    assert schema({})["display_app_offline_timeout"] == value


@pytest.mark.parametrize("value", [-1, 601, True, 1.5, "30", None])
def test_offline_timeout_option_rejects_invalid_seconds(value):
    _, errors, _ = _display_options_form({"display_app_offline_timeout": value}, {})
    assert errors["display_app_offline_timeout"] == "invalid_option_range"


@pytest.mark.parametrize("value, expected", [(None, 30), (0, 0), (120, 120), (True, 30), (999, 30)])
async def test_paired_bootstrap_carries_timeout_and_hdmi_without_enabling_cache(app, value, expected):
    if value is not None:
        app.entry.options["display_app_offline_timeout"] = value
    app.resident = True
    app.saved.update(resident=True, selected_app="com.webos.app.hdmi2", selected_input=0x91)
    view = DisplayAppView(app.hass)
    http = web.Application()
    view.register(app.hass, http, http.router)
    base = f"/api/lg_rs232_ip/display_app/test/{app.token}"
    async with TestClient(TestServer(http)) as client:
        response = await client.get(base + "/index.html?_lg_reload=1")
        assert response.status == 200
        body = await response.text()
        assert f'data-app-version="{APP_VERSION}"' in body
        assert f'data-offline-timeout="{expected}"' in body
        assert 'data-fallback-hdmi="ext://hdmi:2"' in body
        assert "manifest=" not in body
        assert response.headers["Cache-Control"] == "no-store"
        state = await (await client.get(base + "/state")).json()
        assert state["offline_timeout"] == expected
        assert not state["offline_enabled"]
        assert (await client.get(base.replace(app.token, "wrong") + "/index.html")).status == 404
        app.closed = True
        assert (await client.get(base + "/index.html?_lg_reload=2")).status == 404
        app.closed = False
