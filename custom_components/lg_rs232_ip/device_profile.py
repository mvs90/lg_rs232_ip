"""Documented Signage encodings; never infer model support from a shared ACK."""

import re

ASPECT_RATIOS = {"Full Screen": 0x02, "Original": 0x06}

DPM_DELAYS = {
    "Off": 0x00,
    "10 seconds": 0x02,
    "1 minute": 0x04,
    "3 minutes": 0x05,
    "5 minutes": 0x06,
    "10 minutes": 0x07,
}
PM_MODES = {
    "Power Off": 0,
    "Sustain Aspect Ratio": 1,
    "Screen Off": 2,
    "Screen Off Always": 3,
    "Screen Off & Backlight On": 4,
    "Network Ready": 5,
}
PM_STATES = {
    0: "Screen on",
    1: "Screen off",
    2: "Screen off always",
    3: "Sustain aspect ratio",
    4: "Screen off & backlight on",
}
SIGNAGE_PICTURE_MODES = {
    "MALL/QSR": 0,
    "GENERAL": 1,
    "GOV./CORP.": 2,
    "TRANSPORTATION": 3,
    "EDUCATION": 4,
    "EXPERT1": 5,
    "AUTO POWER SAVE": 8,
    "CALIBRATION": 0x11,
    "HOSPITAL": 0x12,
}

# LG webOS 4.0 guide, pp. 22–23/85; older Signage installation guides
# additionally document inversion, color wash and washing bar. Codes are hex.
ISM_METHODS = {
    "off": 0x08,
    "white_wash": 0x04,
    "user_image": 0x90,
    "user_video": 0x91,
    "orbiter": 0x02,
    "inversion": 0x01,
    "color_wash": 0x20,
    "washing_bar": 0x80,
}
ISM_DESCRIPTIONS = {
    "off": "Normal picture; ISM image-retention treatment is disabled.",
    "white_wash": "Displays a full white pattern instead of the programme picture.",
    "user_image": "Displays images previously imported in the LG ISM menu from USB.",
    "user_video": "Plays a video previously imported in the LG ISM menu from USB.",
    "orbiter": "Periodically shifts the picture by four pixels; requires a signal and model support.",
    "inversion": "Inverts picture colours; requires a signal and model support.",
    "color_wash": "Alternates white and colour patterns instead of the programme picture.",
    "washing_bar": "Moves a bar across the picture; available on selected older models.",
}


def ism_methods(model: str | None) -> dict[str, int]:
    """UH5F is indoor: do not offer the webOS 4 outdoor-only Orbiter mode."""
    if is_uh5f(model):
        return {
            key: ISM_METHODS[key]
            for key in ("off", "white_wash", "user_image", "user_video")
        }
    return dict(ISM_METHODS)


def ok_payload(response: str | None) -> str | None:
    """Extract the entire payload, including ASCII, only from a complete OK frame."""
    match = re.fullmatch(
        r"[a-z]\s+[0-9a-f]{2,4}\s+OK([^\r\n]*)x", (response or "").strip(), re.I
    )
    return match.group(1) if match and match.group(1) else None


def decode_model(response: str | None) -> str | None:
    """Model query fv returns hexadecimal ASCII, not a numeric measurement."""
    payload = ok_payload(response)
    if not payload:
        return None
    try:
        model = bytes.fromhex(payload).decode("ascii").rstrip("\x00 ")
    except (ValueError, UnicodeError):
        return None
    return model if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._-]{1,63}", model) else None


def decode_software(response: str | None) -> str | None:
    """Keep LG's three version fields; do not interpret them as an integer."""
    payload = ok_payload(response)
    if payload and re.fullmatch(r"[0-9a-fA-F]{6}", payload):
        return ".".join(payload[i : i + 2].upper() for i in (0, 2, 4))
    return None


def is_uh5f(model: str | None) -> bool:
    """Profile only the identified product family; other series remain generic."""
    return bool(model and re.fullmatch(r"(?:75|86|98)UH5F-H[A-Z]?", model, re.I))
