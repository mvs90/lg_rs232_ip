"""Shared appearance preserves content, isolates overrides and remains offline safe."""

from copy import deepcopy
from types import SimpleNamespace
from aiohttp import web
from custom_components.lg_rs232_ip.layout_api import LayoutBackgroundView
from tests.test_layout_cards import cover
import pytest

from custom_components.lg_rs232_ip.layout_config import make_layout
from custom_components.lg_rs232_ip.layout_library import from_config, validate_library
from custom_components.lg_rs232_ip.layout_themes import default_themes, STYLE_FIELDS
from custom_components.lg_rs232_ip.layouts import DisplayLayouts, LayoutConflict
from tests.test_layouts import layouts  # noqa: F401


def content(scene):
    return [
        {
            key: value
            for key, value in item.items()
            if key not in ("color", "background", "accent_color")
        }
        for item in scene["elements"]
    ]


def test_theme_updates_every_view_without_replacing_content_and_sanitizes_startup():
    config = make_layout()
    library = from_config(config)
    library["views"].append(
        dict(deepcopy(library["views"][1]), id="view_custom", name="Custom")
    )
    library["active_theme"] = "morning"
    style = library["themes"][2]["style"]
    style.update(
        media_background_enabled=True,
        media_background_entity="media_player.sonos",
        media_background_color_source="cover",
        ink="#123456",
    )
    library["views"][3]["theme_override"] = True
    before = deepcopy(library)
    runtime, normalized = validate_library(library, config)
    assert library == before
    for old, view in zip(before["views"], normalized["views"]):
        assert content(view["scene"]) == content(old["scene"])
        assert runtime["scenes"][view["id"]] == view["scene"]
        if view["theme_override"]:
            assert view == old
        else:
            assert view["scene"]["background"] == (
                "dawn" if view["id"] == "startup" else "solar"
            )
            assert view["scene"]["media_background_enabled"] == (
                view["id"] != "startup"
            )
            assert view["scene"]["media_background_entity"] == (
                "" if view["id"] == "startup" else "media_player.sonos"
            )
            for item in view["scene"]["elements"]:
                if item["kind"] != "hdmi":
                    assert item["color"] == "#123456"
    normalized["views"][3]["theme_override"] = False
    _, inherited = validate_library(normalized, runtime)
    assert inherited["views"][3]["scene"]["color"] == style["color"]
    assert content(inherited["views"][3]["scene"]) == content(
        before["views"][3]["scene"]
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda lib: lib.update(active_theme="unknown"),
        lambda lib: lib["themes"].pop(),
        lambda lib: lib["themes"].append(deepcopy(lib["themes"][0])),
        lambda lib: lib["themes"][0]["style"].update(ink="url(javascript:bad)"),
        lambda lib: lib["themes"][0]["style"].update(elements=[]),
        lambda lib: lib["themes"][0]["style"].update(
            media_background_entity="sensor.private"
        ),
        lambda lib: lib["views"][0].update(theme_override="false"),
        lambda lib: lib["themes"][0].update(name="bad\nname"),
        lambda lib: lib["themes"].extend(
            [dict(deepcopy(lib["themes"][0]), id=f"theme_{i}") for i in range(21)]
        ),
    ],
)
def test_invalid_theme_never_reaches_runtime(mutate):
    config = make_layout()
    library = from_config(config)
    mutate(library)
    with pytest.raises(ValueError):
        validate_library(library, config)


def test_old_library_keeps_appearance_until_a_theme_is_chosen():
    config = make_layout("sand")
    library = from_config(config)
    del library["themes"], library["active_theme"]
    for view in library["views"]:
        del view["theme_override"]
    runtime, normalized = validate_library(library, config)
    assert runtime == config
    assert normalized["themes"] == default_themes()
    assert not normalized["active_theme"]
    assert all(not view["theme_override"] for view in normalized["views"])


async def test_theme_selection_persists_and_stale_editor_cannot_undo_it(layouts):
    original = layouts.editor_document()
    await layouts.async_set_theme("sand")
    assert layouts.library["active_theme"] == "sand"
    assert layouts.revision == 1
    await layouts.async_set_theme("sand")
    assert layouts.revision == 1
    with pytest.raises(LayoutConflict):
        await layouts.async_save(original["config"], original["revision"])
    with pytest.raises(ValueError, match="Unknown Studio theme"):
        await layouts.async_set_theme("missing")
    restored = DisplayLayouts(layouts.hass, layouts.entry)
    await restored.async_start()
    try:
        assert restored.library == layouts.library
        assert restored.config == layouts.config
    finally:
        await restored.async_close()


async def test_inactive_theme_images_are_validated_and_retained(layouts):
    library = deepcopy(layouts.library)
    library["themes"][1]["style"].update(image_id="a" * 64, background="image")
    with pytest.raises(ValueError, match="Upload the missing"):
        await layouts.async_save(layouts.config, 0, library)
    assert layouts.revision == 0
    assert set(STYLE_FIELDS).issubset(default_themes()[0]["style"])

    identifier = await layouts.backgrounds.async_upload(cover())
    library["themes"][1]["style"]["image_id"] = identifier
    await layouts.async_save(layouts.config, 0, library)
    api = LayoutBackgroundView(layouts.hass)
    request = {"hass_user": SimpleNamespace(is_admin=True)}
    with pytest.raises(web.HTTPConflict):
        await api.delete(request, "one", identifier)
    library["themes"][1]["style"].update(image_id="", background="solid")
    await layouts.async_save(layouts.config, 1, library)
    await api.delete(request, "one", identifier)
    assert identifier not in await layouts.backgrounds.async_list()
