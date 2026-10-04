"""Layout privacy, validation, persistence, cache bounds and editor authorization."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from homeassistant.core import HomeAssistant, SupportsResponse
import pytest

from custom_components.lg_rs232_ip.layout_config import (
    make_layout,
    presets,
    validate_layout,
)
from custom_components.lg_rs232_ip.layouts import DisplayLayouts, LayoutConflict
from custom_components.lg_rs232_ip.layout_api import (
    LayoutEditorView,
    LayoutListView,
    LayoutValidateView,
)


@pytest.fixture
async def layouts(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    entry = SimpleNamespace(entry_id="one", options={"display_app_enabled": True})
    manager = DisplayLayouts(hass, entry)
    hass.data["lg_rs232_ip"] = {"one": {"name": "LG", "layouts": manager}}
    await manager.async_start()
    yield manager
    await manager.async_close()
    await hass.async_stop(force=True)


@pytest.mark.parametrize("preset", presets(), ids=lambda p: p["id"])
def test_presets_have_valid_independent_signal_and_notification_scenes(preset):
    config = validate_layout(preset["layout"])
    assert len(config["scenes"]) == 7
    assert config["scenes"]["signal"]["elements"][0]["kind"] in ("hdmi", "clock")
    assert not any(
        item["kind"] == "hdmi" for item in config["scenes"]["no_signal"]["elements"]
    )
    config["scenes"]["signal"]["elements"][0]["x"] = 99
    assert preset["layout"]["scenes"]["signal"]["elements"][0]["x"] != 99


@pytest.mark.parametrize(
    "mutation",
    [
        lambda c: c.update(mode="javascript:alert(1)"),
        lambda c: c.update(signal_delay=float("nan")),
        lambda c: c["scenes"]["signal"].update(color="url(https://evil.test)"),
        lambda c: c["scenes"]["signal"]["elements"][0].update(x=50),
        lambda c: c["scenes"]["signal"]["elements"][0].update(font_size=float("inf")),
        lambda c: c["scenes"]["signal"]["elements"].append(
            deepcopy(c["scenes"]["signal"]["elements"][0])
        ),
        lambda c: c["scenes"]["no_signal"]["elements"][1].update(
            entity_id="calendar.private"
        ),
        lambda c: c["scenes"]["no_signal"]["elements"][1].update(
            entity_id="weather.bad/path"
        ),
        lambda c: c["scenes"]["no_signal"]["elements"][1].update(text="x" * 2001),
        lambda c: c["scenes"]["signal"].update(elements=[{}] * 17),
    ],
)
def test_layout_rejects_executable_styles_unbounded_fields_and_invalid_bindings(
    mutation,
):
    config = make_layout()
    mutation(config)
    with pytest.raises(ValueError):
        validate_layout(config)


async def test_save_is_atomic_revision_checked_persistent_and_does_not_enable_app(
    layouts,
):
    config = make_layout("aurora")
    config["enabled"] = True
    layouts.changed = Mock()
    await layouts.async_save(config, 0)
    with pytest.raises(LayoutConflict):
        await layouts.async_save(make_layout("sand"), 0)
    invalid = deepcopy(config)
    invalid["scenes"]["signal"]["elements"][0]["x"] = 100
    with pytest.raises(ValueError):
        await layouts.async_save(invalid, 1)
    saved = await layouts.store.async_load()
    assert saved["revision"] == 1 and saved["config"] == layouts.config
    assert layouts.entry.options == {"display_app_enabled": True}
    layouts.changed.assert_called_once()


async def test_only_selected_scalar_data_and_bounded_weather_calendar_are_shared(
    layouts,
):
    config = make_layout()
    config["enabled"] = True
    config["scenes"]["dashboard"] = deepcopy(config["scenes"]["no_signal"])
    scene = config["scenes"]["dashboard"]["elements"]
    scene[1]["entity_id"] = "weather.home"
    scene[2]["entity_id"] = "calendar.family"
    scene[3]["entity_id"] = "sensor.temperature"
    layouts.hass.states.async_set(
        "sensor.temperature",
        "22",
        {"unit_of_measurement": "°C", "access_token": "secret"},
    )
    layouts.hass.states.async_set(
        "weather.home",
        "sunny",
        {"temperature": 23, "temperature_unit": "°C", "private": "secret"},
    )
    layouts.hass.states.async_set(
        "calendar.family", "off", {"message": "Dinner", "description": "secret"}
    )
    layouts.hass.states.async_set("sensor.private", "secret")
    await layouts.async_save(config, 0)
    values = layouts.payload()["values"]
    assert set(values) == {"sensor.temperature", "weather.home", "calendar.family"}
    assert values["sensor.temperature"]["unit"] == "°C"
    assert "secret" not in str(values)

    async def call(domain, service, data, **kwargs):
        assert kwargs == {"blocking": True, "return_response": True}
        if domain == "calendar":
            return {
                "calendar.family": {
                    "events": [
                        {
                            "summary": "x" * 500,
                            "start": "2026-10-04",
                            "description": "secret",
                        }
                    ]
                    * 30
                }
            }
        return {
            "weather.home": {
                "forecast": [{"condition": "sunny", "temperature": 24}] * 30
            }
        }

    async def service(service_call):
        return await call(
            service_call.domain,
            service_call.service,
            service_call.data,
            blocking=True,
            return_response=True,
        )

    layouts.hass.services.async_register(
        "calendar", "get_events", service, supports_response=SupportsResponse.ONLY
    )
    layouts.hass.services.async_register(
        "weather", "get_forecasts", service, supports_response=SupportsResponse.ONLY
    )
    await layouts.async_refresh_data()
    values = layouts.values()
    assert len(values["calendar.family"]["events"]) == 6
    assert len(values["calendar.family"]["events"][0]["summary"]) == 200
    assert len(values["weather.home"]["forecast"]) == 4
    assert "secret" not in str(values)
    config["enabled"] = False
    await layouts.async_save(config, 1)
    assert (
        layouts.payload() is None and layouts._timer is None and layouts._unsub is None
    )


async def test_removed_binding_cannot_receive_in_flight_calendar_response(layouts):
    config = make_layout()
    config["enabled"] = True
    config["scenes"]["dashboard"]["elements"][2]["entity_id"] = "calendar.family"
    await layouts.async_save(config, 0)
    started, finish = asyncio.Event(), asyncio.Event()

    async def call(*args, **kwargs):
        started.set()
        await finish.wait()
        return {"calendar.family": {"events": [{"summary": "private"}]}}

    async def service(service_call):
        return await call(
            service_call.domain,
            service_call.service,
            service_call.data,
            blocking=True,
            return_response=True,
        )

    layouts.hass.services.async_register(
        "calendar", "get_events", service, supports_response=SupportsResponse.ONLY
    )
    layouts.hass.services.async_register(
        "weather", "get_forecasts", service, supports_response=SupportsResponse.ONLY
    )
    task = asyncio.create_task(layouts.async_refresh_data())
    await started.wait()
    await layouts.async_save(make_layout(), 1)
    finish.set()
    await task
    assert layouts._cache == {} and "calendar.family" not in layouts.values()


async def test_editor_routes_require_admin_and_pairing_token_cannot_edit(layouts):
    @web.middleware
    async def auth(request, handler):
        request["hass_user"] = SimpleNamespace(
            is_admin=request.headers.get("X-Admin") == "yes"
        )
        request["ha_authenticated"] = request.headers.get("X-Auth") == "yes"
        return await handler(request)

    app = web.Application(middlewares=[auth])
    # Real handlers, with HA auth simulated at the HTTP boundary.
    editor, listing, validator = (
        LayoutEditorView(layouts.hass),
        LayoutListView(layouts.hass),
        LayoutValidateView(),
    )
    for view in (editor, listing, validator):
        view.register(layouts.hass, app, app.router)
    assert editor.requires_auth and listing.requires_auth and validator.requires_auth
    async with TestClient(TestServer(app)) as client:
        assert (await client.get("/api/lg_rs232_ip/layouts")).status == 401
        assert (
            await client.post(
                "/api/lg_rs232_ip/layout/one?token=panel-token",
                json={"config": make_layout(), "revision": 0},
            )
        ).status == 401
        headers = {"X-Admin": "yes", "X-Auth": "yes"}
        assert (
            await client.get("/api/lg_rs232_ip/layouts", headers={"X-Auth": "yes"})
        ).status == 403
        catalog = await (
            await client.get("/api/lg_rs232_ip/layouts", headers=headers)
        ).json()
        assert (
            len(catalog["presets"]) == 4 and catalog["entries"][0]["entry_id"] == "one"
        )
        response = await client.post(
            "/api/lg_rs232_ip/layout/one",
            headers=headers,
            json={"config": make_layout(), "revision": 0},
        )
        assert response.status == 200
        assert (
            await client.post(
                "/api/lg_rs232_ip/layout/one",
                headers=headers,
                json={"config": make_layout(), "revision": 0},
            )
        ).status == 409
        assert (
            await client.post(
                "/api/lg_rs232_ip/layout_validate",
                headers=headers,
                json={"config": make_layout()},
            )
        ).status == 200
        assert (
            await client.post(
                "/api/lg_rs232_ip/layout_validate", headers=headers, data=b"x" * 1048577
            )
        ).status == 413
        assert (
            await client.get("/api/lg_rs232_ip/layout/other", headers=headers)
        ).status == 404


async def test_calendar_fallback_uses_ha_timezone_and_preserves_all_day_dates(layouts):
    await layouts.hass.config.async_set_time_zone("Europe/Berlin")
    assert layouts._calendar_date("2026-10-04 18:30:00") == "2026-10-04T18:30:00+02:00"
    assert layouts._calendar_date("2026-10-04") == "2026-10-04"
    assert layouts._calendar_date("2026-13-99 18:30:00") == "2026-13-99 18:30:00"


async def test_bad_stored_layout_fails_closed_without_breaking_device_setup(layouts):
    await layouts.store.async_save({"config": {"enabled": True}, "revision": 9})
    second = DisplayLayouts(layouts.hass, layouts.entry)
    await second.async_start()
    assert second.payload() is None and second.config == make_layout()
    await second.async_close()


async def test_all_scenes_can_be_empty_and_old_documents_gain_independent_dashboard(
    layouts,
):
    config = make_layout()
    del config["scenes"]["dashboard"]
    validated = validate_layout(config)
    assert validated["scenes"]["dashboard"] == validated["scenes"]["no_signal"]
    validated["scenes"]["dashboard"]["elements"].clear()
    assert validated["scenes"]["no_signal"]["elements"]
    for scene in validated["scenes"].values():
        scene["elements"].clear()
    await layouts.async_save(validated, 0)
    assert all(not scene["elements"] for scene in layouts.config["scenes"].values())


async def test_forecast_modes_are_deduplicated_and_sun_coordinates_never_leave_ha(
    layouts,
):
    config = make_layout("morning")
    config["enabled"] = True
    config["sun_entity"] = "sun.test"
    for scene in config["scenes"].values():
        for item in scene["elements"]:
            if item["kind"] == "weather":
                item["entity_id"] = "weather.home"
                item["forecast_count"] = 8 if item["forecast_type"] == "hourly" else 4
    layouts.hass.states.async_set("weather.home", "sunny", {"temperature": 20})
    layouts.hass.states.async_set(
        "sun.test",
        "below_horizon",
        {"elevation": -12, "azimuth": 310, "rising": False, "secret": "hidden"},
    )
    await layouts.async_save(config, 0)
    calls = []

    async def forecasts(call):
        calls.append(call.data["type"])
        return {
            "weather.home": {
                "forecast": [
                    {
                        "datetime": "2026-10-04T12:00:00+00:00",
                        "temperature": 21,
                        "condition": "sunny",
                        "description": "hidden",
                    }
                ]
                * 20
            }
        }

    layouts.hass.services.async_register(
        "weather", "get_forecasts", forecasts, supports_response=SupportsResponse.ONLY
    )
    await layouts.async_refresh_data()
    value = layouts.values()["weather.home"]
    assert sorted(calls) == ["daily", "hourly"]
    assert len(value["forecasts"]["daily"]) == 4
    assert len(value["forecasts"]["hourly"]) == 8
    assert type(value["forecasts"]["hourly"][0]["is_daytime"]) is bool
    assert layouts.payload()["sun"] == {
        "elevation": -12.0,
        "azimuth": 310.0,
        "rising": False,
        "is_daytime": False,
    }
    assert "hidden" not in str(layouts.payload()) and "latitude" not in str(
        layouts.payload()
    )


async def test_unsupported_hourly_forecast_does_not_hide_current_or_daily_weather(
    layouts,
):
    config = make_layout("morning")
    config["enabled"] = True
    for scene in config["scenes"].values():
        for item in scene["elements"]:
            if item["kind"] == "weather":
                item["entity_id"] = "weather.home"
    layouts.hass.states.async_set("weather.home", "sunny", {"temperature": 0})
    await layouts.async_save(config, 0)

    async def forecasts(call):
        if call.data["type"] == "hourly":
            raise ValueError("unsupported")
        return {"weather.home": {"forecast": [{"temperature": 2}]}}

    layouts.hass.services.async_register(
        "weather", "get_forecasts", forecasts, supports_response=SupportsResponse.ONLY
    )
    await layouts.async_refresh_data()
    value = layouts.values()["weather.home"]
    assert value["temperature"] == "0" and value["forecast_unavailable"] == ["hourly"]
    assert value["forecasts"]["daily"][0]["temperature"] == "2"
