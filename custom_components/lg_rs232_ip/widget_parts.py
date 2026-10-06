"""Bounded overrides for the existing visual parts of a widget."""

import math
import re

# Groups keep children relative to their parent: e.g. timeline / elapsed time.
TEXT_PARTS = {
    "clock": {"label", "time", "date"},
    "text": {"label", "text"},
    "entity": {"label", "value", "detail"},
    "status": {"label", "value", "detail"},
    "media": {"label", "title", "artist", "album", "elapsed", "duration", "volume"},
    "weather": {"label", "temperature", "detail"},
    "calendar": {"label", "empty", "detail"},
    "message": {"label", "title", "body"},
    "camera": {"label", "detail"},
    "hdmi": set(),
}
PARTS = {kind: set(keys) for kind, keys in TEXT_PARTS.items()}
PARTS["status"].update({"icon", "badge"})
PARTS["media"].update({"cover", "shade", "progress", "bar", "playback"})
PARTS["camera"].add("picture")
PARTS["weather"].update({"icon", "forecast"})
for number in range(1, 9):
    group = f"forecast_{number}"
    PARTS["weather"].update({group, f"{group}_icon"})
    for field in ("time", "high", "low", "rain"):
        TEXT_PARTS["weather"].add(f"{group}_{field}")
        PARTS["weather"].add(f"{group}_{field}")
for kind in ("calendar", "message"):
    PARTS[kind].add("list")
    for number in range(1, 7):
        group = f"row_{number}"
        PARTS[kind].add(group)
        for field in ("label", "value"):
            TEXT_PARTS[kind].add(f"{group}_{field}")
            PARTS[kind].add(f"{group}_{field}")

FIELDS = {
    "visible",
    "x",
    "y",
    "width",
    "height",
    "font_size",
    "font",
    "font_weight",
    "align",
    "color",
    "opacity",
    "z_index",
    "text",
    "fit",
    "radius",
}


def validate_parts(value, kind):
    if not isinstance(value, dict) or not set(value).issubset(PARTS[kind]):
        raise ValueError("Unknown widget part")
    result = {}
    for key, raw in value.items():
        if not isinstance(raw, dict) or not set(raw).issubset(FIELDS):
            raise ValueError("Invalid widget part properties")
        part = {}
        if "visible" in raw:
            if type(raw["visible"]) is not bool:
                raise ValueError("Invalid widget part visibility")
            part["visible"] = raw["visible"]
        for field, low, high in (
            ("x", 0, 99),
            ("y", 0, 99),
            ("width", 1, 100),
            ("height", 1, 100),
            ("font_size", 1, 100),
            ("opacity", 0, 1),
            ("z_index", 0, 30),
            ("radius", 0, 50),
        ):
            if field in raw:
                number = raw[field]
                if (
                    type(number) not in (int, float)
                    or not math.isfinite(number)
                    or not low <= number <= high
                ):
                    raise ValueError("Invalid widget part dimensions")
                part[field] = number
        box = {"x", "y", "width", "height"}
        if box & set(raw) and (
            not box.issubset(raw)
            or raw["x"] + raw["width"] > 100.01
            or raw["y"] + raw["height"] > 100.01
        ):
            raise ValueError("Widget parts must fit inside their parent")
        for field, choices in (
            ("font", ("sans", "serif", "mono")),
            ("align", ("left", "center", "right")),
            ("font_weight", (400, 500, 600, 700)),
            ("fit", ("contain", "cover", "fill")),
        ):
            if field in raw:
                if raw[field] not in choices:
                    raise ValueError("Invalid widget part style")
                part[field] = raw[field]
        if "color" in raw:
            if not isinstance(raw["color"], str) or not re.fullmatch(
                r"#[a-fA-F0-9]{6}", raw["color"]
            ):
                raise ValueError("Invalid widget part color")
            part["color"] = raw["color"].lower()
        if "text" in raw:
            if (
                key not in TEXT_PARTS[kind]
                or not isinstance(raw["text"], str)
                or len(raw["text"]) > 2000
            ):
                raise ValueError("Only text parts accept a plain text override")
            part["text"] = raw["text"]
        result[key] = part
    return result
