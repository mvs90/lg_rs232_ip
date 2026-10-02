"""Independent LG Professional Display integration."""

import logging
from homeassistant.const import Platform
from homeassistant.helpers.storage import Store
from .const import DOMAIN
from .lg_display import LGDisplay
from .web_manager import LGWebManager
from .controller import DisplayController
from .alerts import LGDisplayAlertState

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [
    Platform.MEDIA_PLAYER,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.CAMERA,
]


async def _async_update_listener(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass, entry):
    hass.data.setdefault(DOMAIN, {})
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    display = LGDisplay(
        entry.data["host"],
        port=entry.data.get("port", 9761),
        power_transition_mode=entry.options.get("power_transition_mode", True),
        power_transition_timeout=entry.options.get("power_transition_timeout", 20),
    )
    display.suppress_osd_during_switch = entry.options.get(
        "suppress_osd_during_switch", False
    )
    controller = DisplayController(hass, entry, display)
    data = hass.data[DOMAIN][entry.entry_id] = {
        "host": entry.data["host"],
        "port": entry.data.get("port", 9761),
        "name": entry.title,
        "lg_display": display,
        "controller": controller,
        "alert_state": LGDisplayAlertState(entry.entry_id),
    }
    if entry.options.get("native_web_enabled", False):
        web = data["web_manager"] = LGWebManager(
            entry.data["host"],
            entry.options["native_web_password"],
            entry.options["native_web_fingerprint"],
            url_store=Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.url_restore"),
        )
        try:
            await web.async_recover_url_settings()
        except Exception:
            _LOGGER.warning("LG URL recovery pending")
    if await display.async_connect() and await display.async_get_power_status() is True:
        await display.async_get_model_name()
        await display.async_get_software_version()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await controller.async_start()
    return True


async def async_unload_entry(hass, entry):
    data = hass.data[DOMAIN][entry.entry_id]
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await data["controller"].async_close()
        if web := data.get("web_manager"):
            await web.async_close()
        await data["lg_display"].async_disconnect()
        hass.data[DOMAIN].pop(entry.entry_id)
        hass.bus.async_fire("lg_rs232_ip_status", {"entry_id": entry.entry_id})
        return True
    return False
