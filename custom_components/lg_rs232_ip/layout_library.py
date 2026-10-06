"""Eight protected views and custom views that each become a display source."""

from copy import deepcopy
import re

from .layout_config import make_layout, validate_layout, validate_startup_scene
from .layout_themes import apply_theme, default_themes, validate_themes

FIXED_VIEWS = {
    "hdmi_full": "Nur HDMI",
    "dashboard": "Dashboard",
    "pip_view": "Dashboard PiP",
    "media_view": "Mediaplayer",
    "startup": "Startanzeige",
    "overlay": "Mitteilung",
    "pip": "Mitteilung PiP",
    "fullscreen": "Mitteilung Vollbild",
}
SOURCE_VIEWS = {
    key: FIXED_VIEWS[key] for key in ("dashboard", "pip_view", "media_view")
}
MAX_VIEWS = 32  # Eight fixed views plus up to 24 custom sources.
CUSTOM_ID = re.compile(r"view_[a-zA-Z0-9_-]{1,35}")


def from_config(config):
    return {
        "library_version": 4,
        "themes": default_themes(),
        "active_theme": "",
        "views": [
            {"id": key, "name": name, "theme_override": False, "scene": deepcopy(config["scenes"][key])}
            for key, name in FIXED_VIEWS.items()
        ],
    }


def upgrade_library(value, settings):
    """Keep the user's previously assigned designs when adopting fixed slots."""
    if value.get("library_version") == 4:
        return deepcopy(value)
    if value.get("library_version") in (2, 3):
        result = deepcopy(value)
        result["library_version"] = 4
        defaults = from_config(settings)["views"]
        if value["library_version"] == 2:
            result["views"].insert(0, defaults[0])
        if not any(view["id"] == "startup" for view in result["views"]):
            result["views"].insert(4, next(view for view in defaults if view["id"] == "startup"))
        return result
    by_id = {view["id"]: view for view in value["views"]}
    assignments = value.get("assignments", {})
    assignments = {"pip_view": assignments.get("signal", ""), **assignments}
    result = from_config(settings)
    used = set()
    for view in result["views"]:
        old_id = assignments.get(view["id"])
        if old_id in by_id:
            view["scene"] = deepcopy(by_id[old_id]["scene"])
            used.add(old_id)
    for old in value["views"]:
        if old["id"] in used:
            continue
        copy = deepcopy(old)
        identifier = "view_" + old["id"][:30]
        base, suffix = identifier, 2
        while any(view["id"] == identifier for view in result["views"]):
            identifier = base + "_" + str(suffix)
            suffix += 1
        copy["id"] = identifier
        result["views"].append(copy)
    return result


def validate_library(value, settings):
    if (
        not isinstance(value, dict)
        or value.get("library_version") != 4
        or not isinstance(value.get("views"), list)
        or "assignments" in value
    ):
        raise ValueError("Supply a fixed-view library (version 4)")
    if len(value["views"]) > MAX_VIEWS:
        raise ValueError("Use at most 24 custom views")
    active = value.get("active_theme", "")
    themes = validate_themes(value.get("themes", default_themes()), active)
    theme = next((row for row in themes if row["id"] == active), None)
    views, ids = [], set()
    for raw in value["views"]:
        if not isinstance(raw, dict):
            raise ValueError("Invalid view")
        identifier, name = raw.get("id"), raw.get("name")
        if (
            not isinstance(identifier, str)
            or (identifier not in FIXED_VIEWS and not CUSTOM_ID.fullmatch(identifier))
            or identifier in ids
        ):
            raise ValueError("View IDs must be unique")
        if (
            not isinstance(name, str)
            or not name.strip()
            or len(name) > 80
            or any(ord(c) < 32 for c in name)
        ):
            raise ValueError("Use a view name with 1–80 characters")
        if identifier in FIXED_VIEWS and name != FIXED_VIEWS[identifier]:
            raise ValueError("Fixed views cannot be renamed")
        ids.add(identifier)
        candidate = make_layout()
        candidate["scenes"]["dashboard"] = raw.get("scene")
        normalized = validate_layout(candidate)["scenes"]["dashboard"]
        override = raw.get("theme_override", False)
        if type(override) is not bool:
            raise ValueError("Invalid theme override")
        if identifier == "startup":
            validate_startup_scene(normalized)
        if theme and not override:
            normalized = apply_theme(normalized, theme, startup=identifier == "startup")
        views.append({"id": identifier, "name": name.strip(), "theme_override": override, "scene": normalized})
    if not set(FIXED_VIEWS).issubset(ids):
        raise ValueError("Fixed views cannot be deleted")
    by_id = {view["id"]: view for view in views}
    views = [by_id[key] for key in FIXED_VIEWS] + [
        view for view in views if view["id"] not in FIXED_VIEWS
    ]
    config = deepcopy(settings)
    config["scenes"] = {
        key: deepcopy(settings["scenes"][key]) for key in ("signal", "no_signal")
    }
    config["scenes"].update({view["id"]: deepcopy(view["scene"]) for view in views})
    return validate_layout(config), {"library_version": 4, "views": views, "themes": themes, "active_theme": active}


def sync_legacy(library, config):
    """A runtime editor can update layouts, but cannot remove protected views."""
    result = deepcopy(library)
    for view in result["views"]:
        if view["id"] in config["scenes"]:
            if view["scene"] != config["scenes"][view["id"]] and result.get("active_theme"):
                # Legacy saves have no inheritance control: preserve their explicit edit.
                view["theme_override"] = True
            view["scene"] = deepcopy(config["scenes"][view["id"]])
    return validate_library(result, config)[1]


def source_views(library):
    return {
        view["id"]: view["name"]
        for view in library["views"]
        if view["id"] in SOURCE_VIEWS or view["id"] not in FIXED_VIEWS
    }


def source_names(views, occupied):
    """Keep all HDMI, fixed and user-defined source labels unambiguous."""
    used, result = set(occupied), {}
    for key, title in views.items():
        name = title
        while name in used:
            name += " (App)"
        used.add(name)
        result[key] = name
    return result
