"""Named, reusable views and their assignment to display contexts."""

from copy import deepcopy
import re

from .layout_config import SCENES, make_layout, validate_layout

MAX_VIEWS = 24
SCENE_NAMES = {
    "signal": "Mit HDMI",
    "no_signal": "Ohne HDMI",
    "dashboard": "Dashboard",
    "overlay": "Meldung · Overlay",
    "pip": "Meldung · PiP",
    "fullscreen": "Meldung · Vollbild",
    "pip_view": "PiP",
    "media_view": "Mediaplayer",
}


def from_config(config):
    return {
        "views": [
            {
                "id": key,
                "name": SCENE_NAMES[key],
                "scene": deepcopy(config["scenes"][key]),
            }
            for key in SCENES
        ],
        "assignments": {key: key for key in SCENES},
    }


def validate_library(value, settings):
    if not isinstance(value, dict) or not isinstance(value.get("views"), list):
        raise ValueError("Supply a view library")
    if len(value["views"]) > MAX_VIEWS:
        raise ValueError("Use at most 24 saved views")
    views, ids = [], set()
    for raw in value["views"]:
        if not isinstance(raw, dict):
            raise ValueError("Invalid view")
        identifier, name = raw.get("id"), raw.get("name")
        if (
            not isinstance(identifier, str)
            or not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", identifier)
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
        ids.add(identifier)
        candidate = make_layout()
        candidate["scenes"]["dashboard"] = raw.get("scene")
        normalized = validate_layout(candidate)["scenes"]["dashboard"]
        views.append({"id": identifier, "name": name.strip(), "scene": normalized})
    assignments = value.get("assignments")
    if isinstance(assignments, dict) and set(assignments) in (
        set(SCENES) - {"media_view"},
        set(SCENES) - {"media_view", "pip_view"},
    ):
        assignments = {**assignments, "media_view": ""}
    if isinstance(assignments, dict) and set(assignments) == set(SCENES) - {"pip_view"}:
        # Keep the existing HDMI composition available as the explicit PiP view.
        assignments = {**assignments, "pip_view": assignments["signal"]}
    if not isinstance(assignments, dict) or set(assignments) != set(SCENES):
        raise ValueError("Assign each display context")
    if any(
        not isinstance(v, str) or (v and v not in ids) for v in assignments.values()
    ):
        raise ValueError("Assigned view does not exist")
    library = {"views": views, "assignments": dict(assignments)}
    config = deepcopy(settings)
    defaults = make_layout()["scenes"]
    by_id = {v["id"]: v["scene"] for v in views}
    config["scenes"] = {
        key: deepcopy(by_id.get(assignments[key], defaults[key])) for key in SCENES
    }
    # Also enforce the combined active-entity bound across assigned views.
    return validate_layout(config), library


def sync_legacy(library, config):
    """Keep saved views when older editor/API clients change a runtime scene."""
    result = deepcopy(library)
    defaults = make_layout()["scenes"]
    for key in SCENES:
        identifier = result["assignments"].get(key, "")
        view = next((v for v in result["views"] if v["id"] == identifier), None)
        if view and view["scene"] == config["scenes"][key]:
            continue
        if not identifier and config["scenes"][key] == defaults[key]:
            continue
        if view and list(result["assignments"].values()).count(identifier) == 1:
            view["scene"] = deepcopy(config["scenes"][key])
        else:
            identifier = "legacy_" + key
            ids = {v["id"] for v in result["views"]}
            suffix = 1
            while identifier in ids:
                identifier = f"legacy_{key}_{suffix}"
                suffix += 1
            result["views"].append(
                {
                    "id": identifier,
                    "name": SCENE_NAMES[key],
                    "scene": deepcopy(config["scenes"][key]),
                }
            )
            result["assignments"][key] = identifier
    return validate_library(result, config)[1]
