"""Config flow for LG Display RS232/IP integration."""

import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DEFAULT_PORT, DOMAIN
from .web_manager import normalize_fingerprint


_LOGGER = logging.getLogger(__name__)


class LGDisplayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LG Display RS232/IP."""

    VERSION = 2

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
                await self.async_set_unique_id(
                    f"{user_input[CONF_HOST].lower()}:{user_input[CONF_PORT]}"
                )
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
    """Display settings only; AV entities belong to AV Companion."""

    def __init__(self, entry):
        self._config_entry = entry

    async def async_step_init(self, user_input=None):
        errors = {}
        values = dict(self._config_entry.options if user_input is None else user_input)
        ranges = {
            "polling_interval": (1, 3600, 30),
            "preview_interval": (10, 3600, 30),
            "display_wake_timeout": (5, 300, 60),
            "power_transition_timeout": (0, 300, 20),
        }
        booleans = {
            "power_transition_mode": True,
            "show_input_hdmi1": True,
            "show_input_hdmi2": True,
            "show_input_hdmi3": True,
            "notification_wake_display": False,
            "quiet_hours_enabled": False,
            "native_web_enabled": False,
            "preview_enabled": False,
            "suppress_osd_during_switch": False,
        }
        if user_input is not None:
            for key, (low, high, default) in ranges.items():
                value = values.get(key, default)
                if type(value) is not int or not low <= value <= high:
                    errors[key] = (
                        "invalid_preview_interval"
                        if key == "preview_interval"
                        else "invalid_option_range"
                    )
            if not values.get("native_web_password") and self._config_entry.options.get(
                "native_web_password"
            ):
                values["native_web_password"] = self._config_entry.options[
                    "native_web_password"
                ]
            if values.get("preview_enabled") and not values.get("native_web_enabled"):
                errors["preview_enabled"] = "preview_requires_web"
            if values.get("native_web_enabled"):
                if not values.get("native_web_password"):
                    errors["native_web_password"] = "invalid_native_web_settings"
                try:
                    values["native_web_fingerprint"] = normalize_fingerprint(
                        values.get("native_web_fingerprint", "")
                    )
                except ValueError:
                    errors["native_web_fingerprint"] = "invalid_native_web_settings"
            from homeassistant.util import dt as dt_util

            for key in ("quiet_hours_start", "quiet_hours_end"):
                if dt_util.parse_time(values.get(key, "00:00")) is None:
                    errors[key] = "invalid_time"
            if not errors:
                return self.async_create_entry(title="", data=values)
        schema = {
            vol.Optional(key, default=values.get(key, default)): int
            for key, (_, _, default) in ranges.items()
        }
        schema.update(
            {
                vol.Optional(key, default=values.get(key, default)): bool
                for key, default in booleans.items()
            }
        )
        for key, default in {
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "07:00",
            "native_web_fingerprint": "",
            **{f"input_name_hdmi{i}": f"HDMI {i}" for i in range(1, 4)},
        }.items():
            schema[vol.Optional(key, default=values.get(key, default))] = str
        schema[vol.Optional("native_web_password")] = selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        )
        schema[
            vol.Optional("preview_height", default=values.get("preview_height", "720"))
        ] = vol.In(["360", "720", "1080"])
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(schema), errors=errors
        )
