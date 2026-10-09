"""HA outage configuration and the paired bootstrap needed by the resident app."""

from types import SimpleNamespace

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


async def test_studio_bundle_marker_tracks_bound_provider_not_stale_file_header(app):
    layouts = SimpleNamespace(changed=None)
    assets = {"layout.js": b'window.DisplayStudioRuntimeVersion = "1.2.1";\nwindow.LGLayoutRenderer = function () {};'}
    original = assets["layout.js"]
    app.bind_studio("studio", layouts, assets, "1.4.0")
    assert app.studio_version == "1.4.0"
    assert app.assets["layout.js"].endswith(b'window.DisplayStudioRuntimeVersion = "1.4.0";\n')
    assert assets["layout.js"] == original
    digest = app.asset_digest
    app.bind_studio("studio", layouts, assets, "1.4.1")
    assert app.assets["layout.js"].count(b'"1.4.0"') == 0
    assert app.assets["layout.js"].endswith(b'window.DisplayStudioRuntimeVersion = "1.4.1";\n')
    assert app.asset_digest != digest
    app.unbind_studio("studio")
    assert not app.assets["layout.js"]
    assert app.studio_version is None
