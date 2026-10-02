"""Independent LG Professional Display integration."""

import logging
from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from .const import DOMAIN
from .lg_display import LGDisplay
from .web_manager import LGWebManager
from .controller import DisplayController
from .alerts import LGDisplayAlertState

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [
    Platform.MEDIA_PLAYER,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.CAMERA,
    Platform.BUTTON,
]


async def async_setup(hass, config):
    from .frontend import async_register_card

    await async_register_card(hass)
    from .display_app import DisplayAppView

    hass.http.register_view(DisplayAppView(hass))
    return True


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
    recovery = await Store(
        hass, 1, f"{DOMAIN}.{entry.entry_id}.display_app"
    ).async_load()
    native_enabled = entry.options.get("native_web_enabled", False)
    if native_enabled or (
        recovery and "previous" in recovery and entry.options.get("native_web_password")
    ):
        web = data["web_manager" if native_enabled else "recovery_web"] = LGWebManager(
            entry.data["host"],
            entry.options["native_web_password"],
            entry.options.get("native_web_fingerprint", ""),
            url_store=Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.url_restore"),
            verify_certificate=entry.options.get("native_web_verify_certificate", True),
        )
        try:
            await web.async_recover_url_settings()
        except Exception:
            _LOGGER.warning("LG URL recovery pending")
        from .display_app import DisplayAppManager

        app = data["display_app"] = DisplayAppManager(hass, entry, controller, web)
        await app.async_start()
        try:
            if (
                not app.resident
                or not app.saved.get("resident")
                or app.saved.get("installed", {}).get("fqdnAddr") != app.url()
            ):
                async with controller._control_lock:
                    await app.async_recover_si()
        except Exception:
            _LOGGER.warning(
                "LG SI recovery pending; use Restore SI settings when awake"
            )
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
        if app := data.get("display_app"):
            await app.async_close()
        if web := data.get("web_manager") or data.get("recovery_web"):
            await web.async_close()
        await data["lg_display"].async_disconnect()
        hass.data[DOMAIN].pop(entry.entry_id)
        hass.bus.async_fire("lg_rs232_ip_status", {"entry_id": entry.entry_id})
        return True
    return False
