"""Widget parts are declarative, bounded and retained across theme/offline saves."""

from copy import deepcopy
import pytest
from custom_components.lg_rs232_ip.layout_config import (
    element,
    make_layout,
    validate_layout,
)
from custom_components.lg_rs232_ip.layout_library import from_config, validate_library
from custom_components.lg_rs232_ip.widget_parts import PARTS, TEXT_PARTS
from tests.test_layouts import layouts  # noqa: F401


def example(kind="clock"):
    config = make_layout()
    item = element(kind, 0, 0, 100, 100)
    config["scenes"]["dashboard"]["elements"] = [item]
    return config, item


@pytest.mark.parametrize("kind", PARTS)
def test_every_part_roundtrips_with_bounded_styles(kind):
    config, item = example(kind)
    item["parts"] = {
        key: dict(
            visible=True,
            x=10,
            y=10,
            width=80,
            height=80,
            font_size=15,
            font="serif",
            font_weight=600,
            align="center",
            color="#aabbcc",
            opacity=0.7,
            z_index=3,
            radius=5,
            fit="contain",
        )
        for key in PARTS[kind]
    }
    for key in TEXT_PARTS[kind]:
        item["parts"][key]["text"] = "<script>literal text</script>"
    if kind == "clock":
        item.update(clock_time_format="12h", clock_date_format="weekday")
    assert validate_layout(config)["scenes"]["dashboard"]["elements"][0] == item


@pytest.mark.parametrize(
    "part",
    [
        {"unknown": {}},
        {"time": {"x": 2}},
        {"time": {"visible": "false"}},
        {"time": {"font_size": float("inf")}},
        {"time": {"font_size": float("nan")}},
        {"time": {"font": "url(https://outside)"}},
        {"time": {"onclick": "code"}},
        {"time": {"color": "red;display:none"}},
        {"time": {"font_weight": 123}},
        {"time": {"x": 80, "y": 10, "width": 30, "height": 20}},
        {"time": {"text": "a" * 2001}},
        {"time": {"height": True}},
    ],
)
def test_invalid_parts_are_rejected(part):
    config, item = example()
    item["parts"] = part
    with pytest.raises(ValueError):
        validate_layout(config)


def test_non_text_parts_do_not_allow_replacing_the_decoder_or_cover_dom():
    for kind, key in (("media", "cover"), ("media", "progress"), ("camera", "picture")):
        config, item = example(kind)
        item["parts"] = {key: {"text": "not allowed"}}
        with pytest.raises(ValueError):
            validate_layout(config)


def test_themes_preserve_part_geometry_fonts_and_visibility_but_inherit_colours():
    config, item = example()
    item["parts"] = {
        "time": {"visible": False},
        "date": {
            "font_size": 15,
            "font": "serif",
            "color": "#123456",
            "x": 10,
            "y": 30,
            "width": 80,
            "height": 40,
        },
    }
    library = from_config(config)
    library["active_theme"] = "aurora"
    expected = deepcopy(item["parts"])
    del expected["date"]["color"]
    runtime, _ = validate_library(library, config)
    assert runtime["scenes"]["dashboard"]["elements"][0]["parts"] == expected
    library["views"][1]["theme_override"] = True
    runtime, _ = validate_library(library, config)
    assert runtime["scenes"]["dashboard"]["elements"][0]["parts"] == item["parts"]


async def test_offline_startup_preserves_local_clock_parts_and_changes_bundle_version(
    layouts,
):
    config = deepcopy(layouts.config)
    clock = element("clock", 5, 5, 90, 40)
    clock.update(
        clock_date_format="iso",
        clock_time_format="24h",
        parts={"time": {"visible": False}, "date": {"font": "mono", "font_size": 20}},
    )
    config["scenes"]["startup"]["elements"] = [clock]
    before = layouts.startup_design.version
    await layouts.async_save(config, 0)
    doc = layouts.startup_design.document()
    assert doc["scene"]["elements"][0]["parts"] == clock["parts"]
    assert doc["scene"]["elements"][0]["clock_date_format"] == "iso"
    assert layouts.startup_design.version != before
