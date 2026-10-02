"""Config flow for LG Display RS232/IP integration."""

import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DEFAULT_PORT, DOMAIN, INPUT_SOURCES


def _extract_entity_id(value: Any) -> Optional[str]:
    """Normalize an entity selector value to an entity_id string."""
    if value is None:
        return None

    if isinstance(value, str):
        return value or None

    if isinstance(value, dict):
        entity_id = value.get("entity_id")
        if isinstance(entity_id, str) and entity_id:
            return entity_id

    return None


_LOGGER = logging.getLogger(__name__)


class LGDisplayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LG Display RS232/IP."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle the initial step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            # Validate connection
            try:
                from .lg_display import LGDisplay

                lg = LGDisplay(
                    host=user_input[CONF_HOST],
                    port=user_input[CONF_PORT],
                )
                # Test connection
                if await lg.async_connect():
                    await lg.async_disconnect()
                else:
                    errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.error("Error connecting to LG Display: %s", err)
                errors["base"] = "cannot_connect"

            if not errors:
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Required(CONF_NAME, default="LG Display"): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return LGDisplayOptionsFlow(config_entry)


class LGDisplayOptionsFlow(config_entries.OptionsFlow):
    """Handle options for LG Display."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    def _standby_schema(self, values=None):
        options = values if values is not None else self._config_entry.options
        return {
            vol.Optional(
                "standby_signal_check",
                default=options.get("standby_signal_check", True),
            ): bool,
            vol.Optional(
                "standby_no_signal_seconds",
                default=options.get("standby_no_signal_seconds", 120),
            ): int,
            vol.Optional(
                "standby_idle_seconds", default=options.get("standby_idle_seconds", 900)
            ): int,
        }

    def _get_linked_media_source_options(
        self, linked_entity_value: Any = None
    ) -> list[str]:
        """Return available sources from the configured linked media player."""
        linked_entity_id = _extract_entity_id(
            linked_entity_value
            if linked_entity_value is not None
            else self._config_entry.options.get("linked_media_player_entity_id")
        )

        saved_sources = self._config_entry.options.get(
            "visible_linked_media_sources", []
        )
        ordered_sources: list[str] = []

        def add_source(source: Any) -> None:
            if source is None:
                return
            source_name = str(source).strip()
            if source_name and source_name not in ordered_sources:
                ordered_sources.append(source_name)

        if isinstance(saved_sources, (list, tuple, set)):
            for source in saved_sources:
                add_source(source)

        if linked_entity_id and self.hass is not None:
            state = self.hass.states.get(linked_entity_id)
            if state is not None:
                for source in state.attributes.get("source_list", []) or []:
                    add_source(source)
                add_source(state.attributes.get("source"))
                add_source(state.attributes.get("app_name"))

        return ordered_sources

    async def async_step_init(self, user_input=None):
        """Configure optional links and standby protection without nullable defaults."""
        from homeassistant.helpers import entity_registry as er

        errors = {}
        values = dict(self._config_entry.options if user_input is None else user_input)
        ranges = {
            "polling_interval": (1, 3600, 60, "invalid_polling_range"),
            "power_transition_timeout": (
                0,
                300,
                20,
                "invalid_transition_timeout_range",
            ),
            "media_player_pending_power_seconds": (0, 60, 12, "invalid_pending_range"),
            "media_player_pending_source_seconds": (0, 60, 8, "invalid_pending_range"),
            "power_supply_off_delay_seconds": (
                0,
                300,
                5,
                "invalid_power_supply_off_delay_range",
            ),
        }
        entity_fields = {
            "linked_media_player_entity_id": "media_player",
            "linked_volume_media_player_entity_id": "media_player",
            "power_supply_switch_entity_id": "switch",
        }
        if user_input is not None:
            for key, (low, high, default, error) in ranges.items():
                value = values.get(key, default)
                if type(value) is not int or not low <= value <= high:
                    errors[key] = error
            for key, default in (
                ("standby_no_signal_seconds", 120),
                ("standby_idle_seconds", 900),
            ):
                value = values.get(key, default)
                if type(value) is not int or not (value == 0 or 30 <= value <= 86400):
                    errors[key] = "invalid_standby_timeout"
            registry = er.async_get(self.hass)
            for key in entity_fields:
                entity_id = _extract_entity_id(values.get(key))
                if not entity_id:
                    values.pop(key, None)
                    continue
                values[key] = entity_id
                selected = registry.async_get(entity_id)
                if (
                    selected is not None
                    and selected.config_entry_id == self._config_entry.entry_id
                ):
                    errors[key] = "self_reference"
            if not errors:
                return self.async_create_entry(title="", data=values)

        schema = {}
        for key, (_, _, default, _) in ranges.items():
            schema[vol.Optional(key, default=values.get(key, default))] = int
        for key, default in {
            "power_transition_mode": True,
            "show_input_hdmi1": True,
            "show_input_hdmi2": True,
            "show_input_hdmi3": True,
            "show_linked_app_sources": True,
        }.items():
            schema[vol.Optional(key, default=values.get(key, default))] = bool
        schema.update(self._standby_schema(values))
        for key, domain in entity_fields.items():
            entity_id = _extract_entity_id(values.get(key))
            schema[vol.Optional(key, default=entity_id or vol.UNDEFINED)] = (
                selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=domain, multiple=False)
                )
            )
        for key, default, choices in (
            ("linked_media_player_input", "HDMI 1", list(INPUT_SOURCES)),
            (
                "linked_volume_sync_mode",
                "hdmi1_only",
                ["hdmi1_only", "always", "display_only"],
            ),
        ):
            schema[vol.Optional(key, default=values.get(key, default))] = (
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=choices, mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            )
        for index in range(1, 4):
            key = f"input_name_hdmi{index}"
            schema[vol.Optional(key, default=values.get(key, f"HDMI {index}"))] = str
        sources = self._get_linked_media_source_options(
            values.get("linked_media_player_entity_id")
        )
        schema[
            vol.Optional(
                "visible_linked_media_sources",
                default=values.get("visible_linked_media_sources", sources),
            )
        ] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=sources,
                multiple=True,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(schema), errors=errors
        )
