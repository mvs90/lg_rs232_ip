"""Config flow for LG Display RS232/IP integration."""

import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DEFAULT_PORT, DOMAIN
from .web_manager import (
    LGWebError,
    async_read_certificate_fingerprint,
    normalize_fingerprint,
)


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

                self._connection_data = dict(user_input)
                return await self.async_step_settings()

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

    async def async_step_settings(self, user_input=None):
        """Confirm display options before HA creates the device and asks for an area."""
        if not getattr(self, "_connection_data", None):
            return await self.async_step_user()
        schema, errors, values = _display_options_form(user_input, {})
        if user_input is not None:
            await _async_prepare_web_options(
                self._connection_data[CONF_HOST], values, errors
            )
        if user_input is not None and not errors:
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._connection_data[CONF_NAME],
                data=self._connection_data,
                options=values,
            )
        return self.async_show_form(
            step_id="settings", data_schema=schema, errors=errors
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
        schema, errors, values = _display_options_form(
            user_input, self._config_entry.options
        )
        if user_input is not None:
            await _async_prepare_web_options(
                self._config_entry.data[CONF_HOST], values, errors
            )
        if user_input is not None and not errors:
            return self.async_create_entry(title="", data=values)
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)


async def _async_prepare_web_options(host, values, errors):
    """Auto-enroll only an empty pin; never replace a stored pin on failure."""
    if (
        not errors
        and values.get("native_web_enabled")
        and values.get("native_web_verify_certificate", True)
        and not values.get("native_web_fingerprint")
    ):
        try:
            values["native_web_fingerprint"] = await async_read_certificate_fingerprint(
                host
            )
        except LGWebError:
            errors["native_web_fingerprint"] = "cannot_read_certificate"


def _display_options_form(user_input, saved_options):
    """Share fields, defaults and validation between onboarding and later options."""
    errors = {}
    values = dict(saved_options if user_input is None else user_input)
    ranges = {
        "polling_interval": (1, 3600, 30),
        "preview_interval": (1, 3600, 30),
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
        "native_web_verify_certificate": True,
        "preview_enabled": False,
        "suppress_osd_during_switch": False,
        "display_app_enabled": False,
        "display_app_resident": False,
        "display_app_offline": False,
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
        active = values.get("preview_active_interval", 1)
        if type(active) not in {int, float} or not (active == 0 or 0.5 <= active <= 10):
            errors["preview_active_interval"] = "invalid_option_range"
        if not values.get("native_web_password") and saved_options.get(
            "native_web_password"
        ):
            values["native_web_password"] = saved_options["native_web_password"]
        if values.get("preview_enabled") and not values.get("native_web_enabled"):
            errors["preview_enabled"] = "preview_requires_web"
        if values.get("display_app_enabled") and not values.get("native_web_enabled"):
            errors["display_app_enabled"] = "preview_requires_web"
        if values.get("display_app_base_url"):
            from .display_app import validate_base_url

            try:
                values["display_app_base_url"] = validate_base_url(
                    values["display_app_base_url"]
                )
            except ValueError:
                errors["display_app_base_url"] = "invalid_display_app_url"
        if values.get("display_app_mode", "si") not in {"si", "website"}:
            errors["display_app_mode"] = "invalid_display_app_mode"
        if values.get("display_app_resident") and (
            not values.get("display_app_enabled")
            or values.get("display_app_mode", "si") != "si"
        ):
            errors["display_app_resident"] = "resident_requires_si"
        entities = values.get("display_app_entities", [])
        if (
            not isinstance(entities, list)
            or len(entities) > 12
            or any(
                not isinstance(e, str)
                or e.split(".")[0] not in {"sensor", "binary_sensor"}
                for e in entities
            )
        ):
            errors["display_app_entities"] = "invalid_display_app_entities"
        if values.get("native_web_enabled"):
            if not values.get("native_web_password"):
                errors["native_web_password"] = "invalid_native_web_settings"
            if values.get("native_web_verify_certificate", True) and values.get(
                "native_web_fingerprint"
            ):
                try:
                    values["native_web_fingerprint"] = normalize_fingerprint(
                        values["native_web_fingerprint"]
                    )
                except ValueError:
                    errors["native_web_fingerprint"] = "invalid_native_web_settings"
        from homeassistant.util import dt as dt_util

        for key in ("quiet_hours_start", "quiet_hours_end"):
            if dt_util.parse_time(values.get(key, "00:00")) is None:
                errors[key] = "invalid_time"
    schema = {
        vol.Optional(key, default=values.get(key, default)): int
        for key, (_, _, default) in ranges.items()
    }
    schema[
        vol.Optional(
            "preview_active_interval", default=values.get("preview_active_interval", 1)
        )
    ] = selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0, max=10, step=0.5, mode=selector.NumberSelectorMode.BOX
        )
    )
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
        "display_app_base_url": "",
        **{f"input_name_hdmi{i}": f"HDMI {i}" for i in range(1, 4)},
    }.items():
        schema[vol.Optional(key, default=values.get(key, default))] = str
    schema[vol.Optional("native_web_password")] = selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
    )
    schema[
        vol.Optional("preview_height", default=values.get("preview_height", "720"))
    ] = vol.In(["360", "720", "1080"])
    schema[
        vol.Optional("display_app_mode", default=values.get("display_app_mode", "si"))
    ] = selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=["si", "website"], translation_key="display_app_mode"
        )
    )
    schema[
        vol.Optional(
            "display_app_entities", default=values.get("display_app_entities", [])
        )
    ] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain=["sensor", "binary_sensor"], multiple=True)
    )
    return vol.Schema(schema), errors, values
