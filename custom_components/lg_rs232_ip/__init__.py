"""Independent LG Professional Display integration."""

import logging
from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.helpers import entity_registry as er
from .const import DOMAIN
from .lg_display import LGDisplay
from .web_manager import LGWebManager
from .controller import DisplayController
from .alerts import LGDisplayAlertState
from .system_settings import SystemSettings, validate_setting
from .power_settings import PowerSettings
from .maintenance import MaintenanceSettings
from .picture_settings import PictureSettings
from .hardware_settings import HardwareSettings
from .native_schedules import NativeSchedules

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
    Platform.TEXT,
    Platform.DATETIME,
    Platform.TIME,
]


async def async_setup(hass, config):
    from .frontend import async_register_card

    await async_register_card(hass)
    from .blueprint import install_blueprint

    try:
        await hass.async_add_executor_job(install_blueprint, hass.config.config_dir)
    except OSError:
        _LOGGER.warning("Could not install the optional LG automation blueprint")
    from .display_app import DisplayAppView

    hass.http.register_view(DisplayAppView(hass))
    from .layout_api import (
        LayoutBackgroundView,
        LayoutSuggestionsView,
        LayoutMediaView,
        LayoutLibraryView,
        LayoutEditorView,
        LayoutListView,
        LayoutValidateView,
    )

    hass.http.register_view(LayoutListView(hass))
    hass.http.register_view(LayoutEditorView(hass))
    hass.http.register_view(LayoutValidateView())
    hass.http.register_view(LayoutBackgroundView(hass))
    hass.http.register_view(LayoutSuggestionsView(hass))
    hass.http.register_view(LayoutMediaView(hass))
    hass.http.register_view(LayoutLibraryView(hass))
    return True


async def _async_update_listener(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass, entry):
    hass.data.setdefault(DOMAIN, {})
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    address_store = SystemSettings.address_store(hass, entry)
    saved_address = await address_store.async_load()
    try:
        device_id = int(validate_setting("signageSetId", (saved_address or {}).get("device_id", entry.data.get("device_id", 1))))
    except (ValueError, AttributeError):
        device_id = 1
    display = LGDisplay(
        entry.data["host"],
        port=entry.data.get("port", 9761),
        device_id=device_id,
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
    from .layouts import DisplayLayouts

    layouts = data["layouts"] = DisplayLayouts(hass, entry)
    await layouts.async_start()
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
    if native_enabled:
        settings = data["system_settings"] = SystemSettings(
            hass, entry, display, data["web_manager"], controller, address_store, saved_address
        )
        await settings.async_refresh()
    if await display.async_connect() and await display.async_get_power_status() is True:
        await display.async_get_model_name()
        await display.async_get_software_version()
    power_settings = data["power_settings"] = PowerSettings(hass, entry, display, controller)
    await power_settings.async_refresh()
    hardware = data["hardware_settings"] = HardwareSettings(hass, entry, display, controller)
    await hardware.async_refresh()
    picture = data["picture_settings"] = PictureSettings(hass, entry, display, controller, data.get("web_manager") if native_enabled else None)
    await picture.async_refresh()
    entry.async_on_unload(display.subscribe_picture_settings(
        lambda: hass.async_create_task(picture.async_request_refresh())))
    registry = er.async_get(hass)
    if entity_id := registry.async_get_entity_id("select", DOMAIN, f"{entry.entry_id}_picture_mode"):
        if registry.async_get(entity_id).disabled_by is er.RegistryEntryDisabler.INTEGRATION:
            registry.async_update_entity(entity_id, disabled_by=None)
    if native_enabled:
        maintenance = data["maintenance"] = MaintenanceSettings(hass, entry, display, data["web_manager"], controller)
        await maintenance.async_refresh()
    if native_enabled:
        schedules = data["native_schedules"] = NativeSchedules(hass, entry, display, controller, data["web_manager"])
        await schedules.async_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await controller.async_start()
    return True


async def async_unload_entry(hass, entry):
    data = hass.data[DOMAIN][entry.entry_id]
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await data["controller"].async_close()
        if app := data.get("display_app"):
            await app.async_close()
        await data["layouts"].async_close()
        if web := data.get("web_manager") or data.get("recovery_web"):
            await web.async_close()
        await data["lg_display"].async_disconnect()
        hass.data[DOMAIN].pop(entry.entry_id)
        hass.bus.async_fire("lg_rs232_ip_status", {"entry_id": entry.entry_id})
        return True
    return False
