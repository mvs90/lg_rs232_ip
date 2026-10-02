"""Minimal diagnostics without addresses, entity names, media or credentials."""

from .const import DOMAIN


async def async_get_config_entry_diagnostics(hass, entry):
    data = hass.data[DOMAIN][entry.entry_id]
    display = data["lg_display"]
    player = data.get("controller")
    return {
        "version": 2,
        "model": display.model_name,
        "software_version": display.software_version,
        "connected": display.is_connected,
        "native_web_configured": data.get("web_manager") is not None,
        "osd_restore_error": display.osd_restore_error,
        "intentionally_unpowered": display.is_intentionally_unpowered,
        "recent_query_count": len(display._query_cache),
        "rejected_query_commands": sorted(
            {key[0] + key[1] for key in display._unsupported_until}
        ),
        "signal_present": player.signal if player else None,
        "presentation_active": player._presentation_active if player else False,
        "presentation_queue_size": len(player._presentation_queue) if player else 0,
    }
