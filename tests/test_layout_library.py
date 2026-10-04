"""Named views persist independently; only assigned scenes reach the panel."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import pytest

from custom_components.lg_rs232_ip.layout_api import (
    LayoutLibraryView,
    LayoutBackgroundView,
)
from custom_components.lg_rs232_ip.layout_config import make_layout, element, presets
from custom_components.lg_rs232_ip.layout_library import (
    from_config,
    validate_library,
    sync_legacy,
)
from custom_components.lg_rs232_ip.layouts import DisplayLayouts, LayoutConflict
from tests.test_layouts import layouts
from tests.test_layout_cards import cover


def test_named_library_validation_and_independent_copies():
    config = make_layout("morning")
    library = from_config(config)
    copy = deepcopy(library["views"][2])
    copy.update(id="evening", name="Abend")
    copy["scene"]["color"] = "#112233"
    library["views"].append(copy)
    runtime, normalized = validate_library(library, config)
    assert normalized["views"][2]["scene"]["color"] != "#112233"
    assert runtime["scenes"]["dashboard"]["color"] != "#112233"
    assert next(p for p in presets() if p["id"] == "morning")["name"] == "Sonnenstand"
    assert all(scene["background"] == "solar" for scene in config["scenes"].values())
    for mutation in (
        lambda lib: lib["views"].append(deepcopy(lib["views"][0])),
        lambda lib: lib["views"][0].update(name="  "),
        lambda lib: lib["views"][0].update(id="../outside"),
        lambda lib: lib["views"][0]["scene"].update(color="url(https://bad)"),
        lambda lib: lib["assignments"].update(dashboard="absent"),
        lambda lib: lib.update(views=[dict(copy, id=f"view_{i}") for i in range(25)]),
    ):
        invalid = deepcopy(library)
        mutation(invalid)
        with pytest.raises(ValueError):
            validate_library(invalid, config)


def test_legacy_save_preserves_defaults_and_shared_or_unassigned_views():
    config = make_layout()
    empty = {"views": [], "assignments": {key: "" for key in config["scenes"]}}
    assert sync_legacy(empty, config) == empty
    library = from_config(config)
    library["assignments"]["no_signal"] = "dashboard"
    reserved = deepcopy(library["views"][2])
    reserved.update(id="legacy_dashboard", name="Saved draft")
    library["views"].append(reserved)
    runtime, library = validate_library(library, config)
    runtime["scenes"]["dashboard"]["color"] = "#123456"
    result = sync_legacy(library, runtime)
    assert next(v for v in result["views"] if v["id"] == reserved["id"]) == reserved
    assert result["assignments"]["no_signal"] == "dashboard"
    assert result["assignments"]["dashboard"] == "legacy_dashboard_1"
    compiled, _ = validate_library(result, runtime)
    assert compiled == runtime
    assert sync_legacy(result, runtime) == result


async def test_saved_views_only_publish_assigned_data_and_survive_restart(layouts):
    config = make_layout()
    config["enabled"] = True
    library = from_config(config)
    spare = deepcopy(library["views"][2])
    spare.update(id="private", name="Unbenutzte Ansicht")
    item = element("entity", 5, 5, 40, 40)
    item["entity_id"] = "sensor.private"
    spare["scene"]["elements"] = [item]
    library["views"].append(spare)
    layouts.hass.states.async_set("sensor.private", "secret")
    await layouts.async_save(config, 0, library)
    assert "private" not in str(layouts.payload())
    assert len(layouts.editor_document()["config"]["views"]) == 8
    second = DisplayLayouts(layouts.hass, layouts.entry)
    await second.async_start()
    try:
        assert second.library == layouts.library
        assert second.config == layouts.config
    finally:
        await second.async_close()
    library["assignments"]["dashboard"] = "private"
    await layouts.async_save(config, 1, library)
    assert layouts.payload()["values"]["sensor.private"]["state"] == "secret"
    assert "views" not in layouts.payload()["config"]
    with pytest.raises(LayoutConflict):
        await layouts.async_save(config, 1, library)
    library["views"] = [v for v in library["views"] if v["id"] != "private"]
    library["assignments"]["dashboard"] = ""
    await layouts.async_save(config, 2, library)
    assert "sensor.private" not in layouts.values()
    assert layouts.config["scenes"]["dashboard"] == make_layout()["scenes"]["dashboard"]


async def test_existing_runtime_is_adopted_without_losing_user_bindings(layouts):
    config = make_layout("sand")
    config["scenes"]["dashboard"]["elements"][1]["entity_id"] = "weather.home"
    await layouts.store.async_save({"config": config, "revision": 7})
    second = DisplayLayouts(layouts.hass, layouts.entry)
    await second.async_start()
    try:
        assert second.config == config and second.revision == 7
        assert second.library["views"][2]["scene"] == config["scenes"]["dashboard"]
        # The original storage remains intact until the user saves.
        assert "library" not in await second.store.async_load()
    finally:
        await second.async_close()


async def test_library_api_authorization_and_inactive_background_protection(layouts):
    image_id = await layouts.backgrounds.async_upload(cover())
    editor = layouts.editor_document()["config"]
    extra = deepcopy(editor["views"][2])
    extra.update(id="spare", name="Später")
    extra["scene"]["image_id"] = image_id
    editor["views"].append(extra)

    @web.middleware
    async def auth(request, handler):
        request["ha_authenticated"] = request.headers.get("X-Auth") == "yes"
        request["hass_user"] = SimpleNamespace(
            is_admin=request.headers.get("X-Admin") == "yes"
        )
        return await handler(request)

    app = web.Application(middlewares=[auth])
    for view in (LayoutLibraryView(layouts.hass), LayoutBackgroundView(layouts.hass)):
        view.register(layouts.hass, app, app.router)
    headers = {"X-Auth": "yes", "X-Admin": "yes"}
    async with TestClient(TestServer(app)) as client:
        path = "/api/lg_rs232_ip/layout_library/one"
        assert (await client.get(path)).status == 401
        assert (await client.get(path, headers={"X-Auth": "yes"})).status == 403
        response = await client.post(
            path, headers=headers, json={"config": editor, "revision": 0}
        )
        assert response.status == 200
        assert len((await response.json())["config"]["views"]) == 8
        assert (
            await client.post(
                path, headers=headers, json={"config": editor, "revision": 0}
            )
        ).status == 409
        assert (
            await client.delete(
                f"/api/lg_rs232_ip/layout_background/one/{image_id}", headers=headers
            )
        ).status == 409
        editor["assignments"]["dashboard"] = "deleted"
        assert (
            await client.post(
                path, headers=headers, json={"config": editor, "revision": 1}
            )
        ).status == 400
        assert layouts.revision == 1


async def test_live_sun_updates_are_bounded_published_and_cleaned_up(layouts):
    config = make_layout("morning")
    config["enabled"] = True
    layouts.hass.states.async_set("sun.sun", "above_horizon", {"rising": True})
    await layouts.async_save(config, 0)
    layouts.changed = Mock()
    with (
        patch(
            "custom_components.lg_rs232_ip.layouts.elevation", side_effect=[10, 11]
        ) as elevation,
        patch("custom_components.lg_rs232_ip.layouts.azimuth", side_effect=[120, 121]),
    ):
        assert layouts.sun()["elevation"] == 10
        assert layouts.sun()["elevation"] == 10
        elevation.assert_called_once()
        layouts._sun_timer()
        layouts._sun_tick(None)
        layouts.changed.assert_called_once()
        assert layouts.sun()["elevation"] == 11
        assert layouts.sun()["azimuth"] == 121
        assert "latitude" not in str(layouts.payload())
    assert layouts._sun_timer is not None
    config["enabled"] = False
    await layouts.async_save(config, 1)
    assert layouts._sun_timer is None


def test_29_library_keeps_its_hdmi_composition_as_explicit_pip():
    config = make_layout("morning")
    del config["scenes"]["pip_view"]
    library = from_config(make_layout("morning"))
    library["views"] = [view for view in library["views"] if view["id"] != "pip_view"]
    del library["assignments"]["pip_view"]
    original = deepcopy(library)
    runtime, normalized = validate_library(library, config)
    assert normalized["views"] == original["views"]
    assert normalized["assignments"]["pip_view"] == "signal"
    assert runtime["scenes"]["pip_view"] == config["scenes"]["signal"]
    assert library == original


async def test_legacy_hdmi_scenes_stay_saved_but_do_not_publish_or_request_data(
    layouts,
):
    config = make_layout()
    config["enabled"] = True
    old = element("media", 5, 5, 40, 40)
    old["entity_id"] = "media_player.legacy"
    weather = element("weather", 50, 5, 40, 40)
    weather["entity_id"] = "weather.legacy"
    config["scenes"]["signal"]["elements"] = [old, weather]
    config["scenes"]["no_signal"]["elements"] = [old, weather]
    await layouts.async_save(config, 0)
    assert layouts.document()["config"]["scenes"]["signal"]["elements"]
    assert "signal" not in layouts.payload()["config"]["scenes"]
    assert "no_signal" not in layouts.payload()["config"]["scenes"]
    assert layouts.values() == {} and layouts.media_entities() == set()
    assert layouts.forecast_requests() == {}
