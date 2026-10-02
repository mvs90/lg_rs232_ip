"""Minimal diagnostics without addresses, entity names, media or credentials."""

from .const import DOMAIN


async def async_get_config_entry_diagnostics(hass, entry):
    data = hass.data[DOMAIN][entry.entry_id]
    display = data["lg_display"]
    player = data.get("media_player")
    return {
        "version": 1,
        "connected": display.is_connected,
        "intentionally_unpowered": display.is_intentionally_unpowered,
        "recent_query_count": len(display._query_cache),
        "rejected_query_commands": sorted(
            {key[0] + key[1] for key in display._unsupported_until}
        ),
        "signal_present": player._signal_present if player else None,
        "standby_reason": player._last_standby_reason if player else None,
        "presentation_active": player._presentation_active if player else False,
        "presentation_queue_size": len(player._presentation_queue) if player else 0,
    }
