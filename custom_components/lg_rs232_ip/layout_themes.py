"""Saved visual themes; runtime scenes remain bounded and fully resolved."""

from copy import deepcopy
import re

from .layout_config import COLORS, make_layout, presets, validate_layout

STYLE_FIELDS = (
    "background",
    "color",
    "accent",
    "image_id",
    "image_fit",
    "image_dim",
    "gradient_angle",
    "media_background_enabled",
    "media_background_entity",
    "media_background_fit",
    "media_background_color_source",
    "media_background_dim",
)
PALETTE_FIELDS = ("ink", "surface", "card_accent")
BUILTIN_THEMES = ("cinema", "aurora", "morning", "sand")
MAX_THEMES = 24


def theme_from_scene(identifier, name, scene):
    colors = next((item for item in scene["elements"] if item["kind"] != "hdmi"), {})
    return {
        "id": identifier,
        "name": name,
        "style": {
            **{key: deepcopy(scene[key]) for key in STYLE_FIELDS},
            "ink": colors.get("color", "#f2f6fa"),
            "surface": colors.get("background", "#122333"),
            "card_accent": colors.get("accent_color", scene["accent"]),
        },
    }


def default_themes():
    return [
        theme_from_scene(p["id"], p["name"], p["layout"]["scenes"]["dashboard"])
        for p in presets()
    ]


def validate_themes(value, active):
    if not isinstance(value, list) or not 4 <= len(value) <= MAX_THEMES:
        raise ValueError("Use four built-in themes and at most 20 custom themes")
    result, ids = [], set()
    for raw in value:
        if not isinstance(raw, dict):
            raise ValueError("Invalid theme")
        identifier, name, style = raw.get("id"), raw.get("name"), raw.get("style")
        if (
            not isinstance(identifier, str)
            or identifier in ids
            or (
                identifier not in BUILTIN_THEMES
                and not re.fullmatch(r"theme_[a-zA-Z0-9_-]{1,35}", identifier)
            )
        ):
            raise ValueError("Theme IDs must be unique")
        if (
            not isinstance(name, str)
            or not name.strip()
            or len(name) > 80
            or any(ord(c) < 32 for c in name)
        ):
            raise ValueError("Use a theme name with 1–80 characters")
        if not isinstance(style, dict) or set(style) != set(
            STYLE_FIELDS + PALETTE_FIELDS
        ):
            raise ValueError("A theme contains only background and palette fields")
        candidate = make_layout()
        candidate["scenes"]["dashboard"].update(
            {key: style[key] for key in STYLE_FIELDS}
        )
        normalized = validate_layout(candidate)["scenes"]["dashboard"]
        palette = {}
        for key in PALETTE_FIELDS:
            if not isinstance(style[key], str) or not COLORS.fullmatch(style[key]):
                raise ValueError("Use six-digit theme colors")
            palette[key] = style[key].lower()
        ids.add(identifier)
        result.append(
            {
                "id": identifier,
                "name": name.strip(),
                "style": {**{key: normalized[key] for key in STYLE_FIELDS}, **palette},
            }
        )
    if (
        not set(BUILTIN_THEMES).issubset(ids)
        or not isinstance(active, str)
        or (active and active not in ids)
    ):
        raise ValueError("Built-in themes and the selected theme must exist")
    return result


def apply_theme(scene, theme, *, startup=False):
    result, style = deepcopy(scene), theme["style"]
    result.update({key: deepcopy(style[key]) for key in STYLE_FIELDS})
    if startup:
        if result["background"] == "solar":
            result["background"] = "dawn"
        result["media_background_enabled"] = False
        result["media_background_entity"] = ""
    for item in result["elements"]:
        if item["kind"] != "hdmi":
            for part in item.get("parts", {}).values():
                part.pop("color", None)
            item.update(
                color=style["ink"],
                background=style["surface"],
                accent_color=style["card_accent"],
            )
    return result
