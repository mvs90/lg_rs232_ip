"""LG Display RS232/IP Integration."""

import logging
from datetime import datetime, timezone
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .lg_display import LGDisplay
from .web_manager import LGWebManager

_LOGGER = logging.getLogger(__name__)

DOMAIN = "lg_rs232_ip"
PLATFORMS = [
    Platform.SWITCH,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.MEDIA_PLAYER,
]


def _extract_entity_id(value: Any) -> str | None:
    """Normalize config values that may contain an entity_id dict or string."""
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        entity_id = value.get("entity_id")
        if isinstance(entity_id, str) and entity_id:
            return entity_id
    return None


class LGDisplayAlertState:
    """Store alert and diagnostic events for notification automations."""

    def __init__(self, entry_id: str) -> None:
        self._entry_id = entry_id
        self._active_issues: dict[str, dict[str, Any]] = {}
        self._history: list[dict[str, Any]] = []
        self._listeners: set[Callable[[], None]] = set()
        self._last_event: dict[str, Any] = {
            "code": "ok",
            "message": "OK",
            "level": "info",
            "source": None,
            "trigger": None,
            "details": {},
            "updated_at": self._timestamp(),
        }

    def _timestamp(self) -> str:
        """Return an ISO timestamp for state updates."""
        return datetime.now(timezone.utc).isoformat()

    def subscribe(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Subscribe to alert-state changes."""
        self._listeners.add(listener)

        def _unsubscribe() -> None:
            self._listeners.discard(listener)

        return _unsubscribe

    def _notify(self) -> None:
        """Notify all subscribed entities that the alert state changed."""
        for listener in tuple(self._listeners):
            try:
                listener()
            except Exception:
                _LOGGER.debug("Alert listener callback failed", exc_info=True)

    def _append_history(self, event: dict[str, Any]) -> None:
        """Keep a short rolling history of alert events."""
        self._history.insert(0, event)
        del self._history[10:]

    def set_issue(
        self,
        code: str,
        message: str,
        *,
        level: str = "warning",
        source: str | None = None,
        trigger: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record or update an active issue."""
        issue = {
            "code": code,
            "message": message,
            "level": level,
            "source": source,
            "trigger": trigger,
            "details": details or {},
            "updated_at": self._timestamp(),
        }

        current = self._active_issues.get(code)
        if current is not None:
            comparable_current = dict(current)
            comparable_issue = dict(issue)
            comparable_current.pop("updated_at", None)
            comparable_issue.pop("updated_at", None)
            if comparable_current == comparable_issue:
                return

        self._active_issues[code] = issue
        self._last_event = {**issue, "event": "issue_set"}
        self._append_history(self._last_event)
        self._notify()

    def clear_issue(self, code: str, *, message: str | None = None) -> None:
        """Clear an active issue if it exists."""
        existing = self._active_issues.pop(code, None)
        if existing is None:
            return

        clear_event = {
            "code": code,
            "message": message or f"Resolved: {existing.get('message', code)}",
            "level": "info",
            "source": existing.get("source"),
            "trigger": existing.get("trigger"),
            "details": existing.get("details", {}),
            "updated_at": self._timestamp(),
            "event": "issue_cleared",
        }
        self._last_event = clear_event
        self._append_history(clear_event)
        self._notify()

    @property
    def state(self) -> str:
        """Return the user-visible alert summary."""
        if not self._active_issues:
            return "OK"

        newest_issue = max(
            self._active_issues.values(),
            key=lambda item: str(item.get("updated_at", "")),
        )
        return str(
            newest_issue.get("message") or newest_issue.get("code") or "Issue detected"
        )[:255]

    @property
    def attributes(self) -> dict[str, Any]:
        """Return extended alert details for Home Assistant automations."""
        last_event = self._last_event
        return {
            "entry_id": self._entry_id,
            "level": last_event.get("level", "info"),
            "last_code": last_event.get("code", "ok"),
            "last_message": last_event.get("message", "OK"),
            "last_source": last_event.get("source"),
            "last_trigger": last_event.get("trigger"),
            "updated_at": last_event.get("updated_at"),
            "issue_count": len(self._active_issues),
            "active_issues": list(self._active_issues.values()),
            "history": self._history[:5],
        }


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload integration when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LG Display RS232/IP from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Create a shared display connection for all entities.
    host = entry.data.get("host")
    port = entry.data.get("port")
    lg_display = LGDisplay(
        host=host,
        port=port,
        power_transition_mode=entry.options.get("power_transition_mode", True),
        power_transition_timeout=entry.options.get("power_transition_timeout", 20),
    )

    lg_display.suppress_osd_during_switch = entry.options.get(
        "suppress_osd_during_switch", False
    )

    power_supply_switch_entity_id = _extract_entity_id(
        entry.options.get("power_supply_switch_entity_id")
    )
    skip_initial_display_probe = False
    if power_supply_switch_entity_id:
        power_supply_state = hass.states.get(power_supply_switch_entity_id)
        if power_supply_state is not None and power_supply_state.state == "off":
            lg_display.set_power_supply_state(False)
            skip_initial_display_probe = True
            _LOGGER.info(
                "Skipping LG Display startup probe because power supply switch %s is off",
                power_supply_switch_entity_id,
            )
        elif power_supply_state is not None and power_supply_state.state == "on":
            lg_display.set_power_supply_state(True)

    # Pre-establish the connection at startup so the first entity update is faster.
    if skip_initial_display_probe:
        _LOGGER.debug("Initial LG Display poll skipped due to powered-off supply")
    elif await lg_display.async_connect():
        if await lg_display.async_get_power_status() is True:
            await lg_display.async_get_model_name()
            await lg_display.async_get_software_version()
    else:
        _LOGGER.warning("Could not preconnect to LG Display at %s:%s", host, port)

    hass.data[DOMAIN][entry.entry_id] = {
        "host": entry.data.get("host"),
        "port": entry.data.get("port"),
        "name": entry.data.get("name"),
        "power_transition_mode": entry.options.get("power_transition_mode", True),
        "power_transition_timeout": entry.options.get("power_transition_timeout", 20),
        "sync_automation_enabled": True,
        "lg_display": lg_display,
        "alert_state": LGDisplayAlertState(entry.entry_id),
    }

    if entry.options.get("native_web_enabled", False):
        hass.data[DOMAIN][entry.entry_id]["web_manager"] = LGWebManager(
            host,
            entry.options["native_web_password"],
            entry.options["native_web_fingerprint"],
        )

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data = hass.data[DOMAIN].pop(entry.entry_id)
        if web_manager := data.get("web_manager"):
            await web_manager.async_close()
        lg_display = data.get("lg_display")
        if lg_display is not None:
            await lg_display.async_disconnect()

    return unload_ok
