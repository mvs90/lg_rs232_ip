"""Selected card metadata and room suggestions; never execute entity actions."""

import math
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

DOMAINS = {
    "media_player",
    "sensor",
    "binary_sensor",
    "light",
    "switch",
    "climate",
    "cover",
    "lock",
    "fan",
    "humidifier",
    "vacuum",
    "weather",
    "calendar",
}


def number(value, low=0, high=1_000_000):
    try:
        result = float(value)
        return (
            round(result, 2)
            if math.isfinite(result) and low <= result <= high
            else None
        )
    except (TypeError, ValueError):
        return None


def card_metadata(state):
    attrs = state.attributes
    data = {
        "domain": state.domain,
        "device_class": str(attrs.get("device_class", ""))[:60],
    }
    if state.domain == "media_player":
        for field in (
            "media_title",
            "media_artist",
            "media_album_name",
            "app_name",
            "source",
        ):
            data[field] = str(attrs.get(field) or "")[:200]
        for field, maximum in (
            ("media_duration", 604800),
            ("media_position", 604800),
            ("volume_level", 1),
        ):
            data[field] = number(attrs.get(field), high=maximum)
        data["is_volume_muted"] = attrs.get("is_volume_muted") is True
        data["media_position_updated_at"] = str(
            attrs.get("media_position_updated_at") or ""
        )[:60]
    else:
        for field, low, high in (
            ("brightness", 0, 255),
            ("current_temperature", -100, 200),
            ("temperature", -100, 200),
            ("current_position", 0, 100),
            ("percentage", 0, 100),
        ):
            data[field] = number(attrs.get(field), low, high)
        data["hvac_action"] = str(attrs.get("hvac_action") or "")[:40]
    return data


def room_suggestions(hass, entry_id, area_id=None):
    """Entity area overrides its device area, matching Home Assistant semantics."""
    areas, devices, entities = (
        ar.async_get(hass),
        dr.async_get(hass),
        er.async_get(hass),
    )

    def area(entity):
        device = devices.async_get(entity.device_id) if entity.device_id else None
        return entity.area_id or (device.area_id if device else None)

    default_area = next(
        (
            area(e)
            for e in er.async_entries_for_config_entry(entities, entry_id)
            if e.domain == "media_player" and area(e)
        ),
        None,
    )
    if not default_area:
        default_area = next(
            (
                d.area_id
                for d in dr.async_entries_for_config_entry(devices, entry_id)
                if d.area_id
            ),
            None,
        )
    selected = default_area if area_id is None else area_id
    rooms = sorted(
        [{"area_id": a.id, "name": a.name} for a in areas.async_list_areas()],
        key=lambda a: a["name"].casefold(),
    )
    if selected and not areas.async_get_area(selected):
        raise ValueError("Unknown room")
    candidates = []
    if selected:
        for entity in entities.entities.values():
            if (
                entity.domain not in DOMAINS
                or entity.disabled_by
                or entity.hidden_by
                or entity.entity_category
                or entity.config_entry_id == entry_id
                or area(entity) != selected
            ):
                continue
            state = hass.states.get(entity.entity_id)
            if not state:
                continue
            kind = {
                "media_player": "media",
                "weather": "weather",
                "calendar": "calendar",
            }.get(entity.domain, "status")
            # Prefer room media, climate and meaningful sensors; unavailable devices remain selectable.
            score = {
                "media_player": 0,
                "climate": 1,
                "light": 2,
                "binary_sensor": 3,
                "sensor": 4,
                "cover": 5,
            }.get(entity.domain, 6)
            if state.state in ("unavailable", "unknown"):
                score += 20
            if entity.domain == "sensor" and state.attributes.get("device_class") in (
                "temperature",
                "humidity",
                "carbon_dioxide",
                "pm25",
            ):
                score -= 2
            candidates.append(
                {
                    "entity_id": entity.entity_id,
                    "name": str(
                        state.attributes.get("friendly_name")
                        or entity.name
                        or entity.original_name
                        or entity.entity_id
                    )[:100],
                    "kind": kind,
                    "state": state.state[:100],
                    "unit": str(state.attributes.get("unit_of_measurement") or "")[:30],
                    "device_class": str(state.attributes.get("device_class") or "")[
                        :60
                    ],
                    "score": score,
                }
            )
    candidates.sort(
        key=lambda item: (item["score"], item["name"].casefold(), item["entity_id"])
    )
    return {
        "areas": rooms,
        "area_id": selected,
        "default_area_id": default_area,
        "suggestions": [
            {k: v for k, v in item.items() if k != "score"} for item in candidates[:24]
        ],
        "total": len(candidates),
    }
