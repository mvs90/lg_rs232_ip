"""LG timezone catalog and manual DST rules; no guessed timezone database writes."""

import re
from .maintenance import integer

CONTINENTS = (
    "Africa",
    "Asia",
    "CIS",
    "Europe",
    "MiddleEast",
    "NorthAmerica",
    "Oceania",
    "Pacific",
    "SouthAmerica",
)
DST_FIELDS = {
    "month": (1, 12, "Month"),
    "week": (1, 5, "Week"),
    "weekday": (0, 6, "DayOfWeek"),
    "hour": (0, 23, "Hour"),
}


def region_request(continent, country, timezone):
    if (
        continent not in CONTINENTS
        or not isinstance(country, str)
        or not re.fullmatch("[A-Z]{2}", country)
    ):
        raise ValueError("Select an LG continent and a two-letter country code")
    if not isinstance(timezone, str) or not re.fullmatch(
        r"[A-Za-z0-9_+./-]{1,100}", timezone
    ):
        raise ValueError("Use an LG timezone identifier such as Europe/Berlin")


def dst_request(enabled, fields):
    if not isinstance(enabled, bool) or set(fields) - {
        side + "_" + key for side in ("start", "end") for key in DST_FIELDS
    }:
        raise ValueError("Invalid daylight saving parameters")
    if not fields:
        return {"dstMode": "on" if enabled else "off"}
    result = {"dstMode": "on" if enabled else "off"}
    for side in ("start", "end"):
        for key, (lo, hi, raw) in DST_FIELDS.items():
            result["dst" + side.title() + raw] = str(
                integer(fields.get(side + "_" + key), lo, hi)
            )
    if enabled and all(
        result["dstStart" + raw] == result["dstEnd" + raw]
        for _, _, raw in DST_FIELDS.values()
    ):
        raise ValueError("Daylight saving start and end must differ")
    return result


def normalize_dst(raw):
    try:
        if raw.get("dstMode") not in {"on", "off"}:
            return None
        fields = {
            side + "_" + key: raw["dst" + side.title() + name]
            for side in ("start", "end")
            for key, (_, _, name) in DST_FIELDS.items()
        }
        return dst_request(raw["dstMode"] == "on", fields)
    except (ValueError, TypeError, KeyError, OverflowError):
        return None
