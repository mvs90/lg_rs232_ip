"""Bounded, declarative display layouts. No HTML, templates or executable CSS."""

from copy import deepcopy
import math
import re

SCENES = ("signal", "no_signal", "overlay", "pip", "fullscreen")
KINDS = ("hdmi", "clock", "weather", "calendar", "entity", "text", "message")
BACKGROUNDS = ("solid", "aurora", "dawn", "ocean", "sand", "midnight")
COLORS = re.compile(r"^#[0-9a-fA-F]{6}$")
ENTITY = re.compile(r"^[a-z_]+\.[a-z0-9_]+$")


def element(kind, x, y, width, height):
    return dict(
        id=kind,
        kind=kind,
        x=x,
        y=y,
        width=width,
        height=height,
        label="",
        text="",
        entity_id="",
        font_size=3.2,
        color="#f2f6fa",
        background="#142335",
        opacity=0.88,
        radius=24,
        align="left",
        font="sans",
        show_label=True,
    )


def scene(background="aurora", elements=None, color="#101e30", accent="#6ee7d5"):
    return dict(
        background=background, color=color, accent=accent, elements=elements or []
    )


def _block(kind, x, y, width, height, **values):
    item = element(kind, x, y, width, height)
    item.update(values)
    return item


def make_layout(style="cinema"):
    palettes = {
        "cinema": ("midnight", "#101827", "#8fb6ff"),
        "aurora": ("aurora", "#0b2228", "#79e5c0"),
        "morning": ("dawn", "#382033", "#ffcfaa"),
        "sand": ("sand", "#e9e0cf", "#76654c"),
    }
    background, color, accent = palettes[style]
    light = style == "sand"
    ink, surface = ("#302c26", "#fffaf0") if light else ("#f2f6fa", "#122333")

    def block(kind, x, y, w, h, **kw):
        return _block(kind, x, y, w, h, color=ink, background=surface, **kw)

    overview = [
        block("clock", 5, 6, 40, 30, font_size=10, opacity=0, label="ZUHAUSE"),
        block("weather", 64, 7, 31, 28, label="Draußen", font_size=5),
        block("calendar", 5, 44, 53, 48, label="Was ansteht", font_size=3.3),
        block("entity", 64, 42, 31, 22, label="Raumklima", font_size=5),
        block(
            "text",
            64,
            70,
            31,
            22,
            label="WILLKOMMEN",
            text="Ein guter Ort, um anzukommen.",
            font_size=3,
        ),
    ]
    hdmi = _block("hdmi", 0, 0, 100, 100, opacity=0, radius=0)
    signal = (
        [deepcopy(hdmi)]
        if style == "cinema"
        else [
            block("clock", 4, 4, 27, 24, font_size=8, opacity=0),
            block("weather", 4, 34, 27, 26, label="Draußen", font_size=4.5),
            block("calendar", 4, 65, 27, 30, label="Als Nächstes", font_size=2.6),
            _block("hdmi", 35, 8, 61, 61, opacity=0, radius=0),
            block("entity", 35, 75, 28, 20, label="Zuhause", font_size=4),
            block(
                "text",
                67,
                75,
                29,
                20,
                text="Schön, dass du da bist.",
                opacity=0,
                font_size=3,
            ),
        ]
    )
    overlay = [deepcopy(hdmi), block("message", 60, 65, 36, 30, font_size=3.2)]
    pip = [
        _block("hdmi", 38, 24, 58, 58, opacity=0, radius=0),
        block("message", 4, 15, 30, 70, font_size=3.5),
        block("clock", 67, 3, 29, 17, font_size=5, opacity=0),
    ]
    fullscreen = [
        block("message", 8, 14, 84, 70, font_size=6, opacity=0),
        block("clock", 66, 2, 30, 12, font_size=4, opacity=0),
    ]
    return {
        "schema": 1,
        "enabled": False,
        "mode": "auto",
        "signal_delay": 5,
        "scenes": {
            key: scene(background, items, color, accent)
            for key, items in zip(SCENES, (signal, overview, overlay, pip, fullscreen))
        },
    }


def presets():
    return [
        dict(id=key, name=name, description=description, layout=make_layout(key))
        for key, name, description in (
            (
                "cinema",
                "Cinema",
                "HDMI im Vollbild · dezente Meldungen · Übersicht ohne Signal",
            ),
            (
                "aurora",
                "Aurora",
                "Grüne Lichtflächen · HDMI neben Uhr, Wetter und Terminen",
            ),
            ("morning", "Morgenlicht", "Warme Farben · ein ruhiger Start in den Tag"),
            (
                "sand",
                "Paper & Sand",
                "Helle Flächen · klare Typografie · natürliche Farben",
            ),
        )
    ]


def _number(value, low, high):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not low <= value <= high
    ):
        raise ValueError(f"Number must be between {low} and {high}")
    return round(value, 2)


def _text(value, limit):
    if (
        not isinstance(value, str)
        or len(value) > limit
        or any(ord(c) < 32 and c not in "\n\t" for c in value)
    ):
        raise ValueError("Invalid or oversized text")
    return value


def _choice(value, choices):
    if value not in choices:
        raise ValueError("Unsupported layout value")
    return value


def _color(value):
    if not isinstance(value, str) or not COLORS.fullmatch(value):
        raise ValueError("Use a six-digit hex color")
    return value.lower()


def validate_layout(value):
    if (
        not isinstance(value, dict)
        or value.get("schema") != 1
        or type(value.get("enabled")) is not bool
    ):
        raise ValueError("Unsupported layout document")
    result = dict(
        schema=1,
        enabled=value["enabled"],
        mode=_choice(value.get("mode"), ("auto", "signal", "no_signal")),
        signal_delay=_number(value.get("signal_delay"), 0, 30),
        scenes={},
    )
    if not isinstance(value.get("scenes"), dict):
        raise ValueError("Supply all five layout scenes")
    entities = set()
    for key in SCENES:
        raw = value.get("scenes", {}).get(key)
        if (
            not isinstance(raw, dict)
            or not isinstance(raw.get("elements"), list)
            or len(raw["elements"]) > 16
        ):
            raise ValueError("Each scene supports at most 16 elements")
        normalized = scene(
            _choice(raw.get("background"), BACKGROUNDS),
            [],
            _color(raw.get("color")),
            _color(raw.get("accent")),
        )
        ids, hdmi, messages = set(), 0, 0
        for item in raw["elements"]:
            if not isinstance(item, dict):
                raise ValueError("Invalid element")
            kind = _choice(item.get("kind"), KINDS)
            identifier = _text(item.get("id"), 40)
            if (
                not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", identifier)
                or identifier in ids
            ):
                raise ValueError("Element IDs must be unique within a scene")
            ids.add(identifier)
            hdmi += kind == "hdmi"
            messages += kind == "message"
            obj = dict(id=identifier, kind=kind)
            for field in ("x", "y", "width", "height"):
                obj[field] = _number(
                    item.get(field), 2 if field in ("width", "height") else 0, 100
                )
            if obj["x"] + obj["width"] > 100.01 or obj["y"] + obj["height"] > 100.01:
                raise ValueError("Elements must fit inside the screen")
            obj.update(
                label=_text(item.get("label", ""), 100),
                text=_text(item.get("text", ""), 2000),
                color=_color(item.get("color")),
                background=_color(item.get("background")),
                font_size=_number(item.get("font_size"), 1, 18),
                opacity=_number(item.get("opacity"), 0, 1),
                radius=_number(item.get("radius"), 0, 80),
                font=_choice(item.get("font"), ("sans", "serif", "mono")),
                align=_choice(item.get("align"), ("left", "center", "right")),
            )
            if type(item.get("show_label")) is not bool:
                raise ValueError("Invalid label visibility")
            obj["show_label"] = item["show_label"]
            entity_id = _text(item.get("entity_id", ""), 255)
            if entity_id:
                if not ENTITY.fullmatch(entity_id) or kind not in (
                    "entity",
                    "weather",
                    "calendar",
                ):
                    raise ValueError("Invalid entity binding")
                if kind in ("weather", "calendar") and not entity_id.startswith(
                    kind + "."
                ):
                    raise ValueError("Select a matching weather/calendar entity")
                entities.add(entity_id)
            obj["entity_id"] = entity_id
            normalized["elements"].append(obj)
        if (
            hdmi > 1
            or messages > 1
            or (key in ("overlay", "pip", "fullscreen") and messages != 1)
        ):
            raise ValueError(
                "Use one HDMI element at most, and one message element per notification scene"
            )
        result["scenes"][key] = normalized
    if len(entities) > 32:
        raise ValueError("Select no more than 32 distinct entities")
    return result


def layout_entities(config):
    return {
        item["entity_id"]
        for scene in config["scenes"].values()
        for item in scene["elements"]
        if item["entity_id"]
    }
