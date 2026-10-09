"""Serve the bundled dashboard card through Home Assistant's frontend."""

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig

CARD_VERSION = "2.32.1"
CARD_PATH = "/lg_rs232_ip/lg-display-remote.js"
CARD_URL = f"{CARD_PATH}?v={CARD_VERSION}"
SETTINGS_URL = f"/lg_rs232_ip/device-settings.js?v={CARD_VERSION}"


async def async_register_card(hass):
    """Called once by integration setup, independent of the number of displays."""
    root = Path(__file__).parent / "www"
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                CARD_PATH,
                str(root / "lg-display-remote.js"),
                False,
            ),
            StaticPathConfig(
                "/lg_rs232_ip/device-settings.js", str(root / "device-settings.js"), False
            ),
            StaticPathConfig(
                "/lg_rs232_ip/device-menu.json", str(root / "device-menu.json"), False
            ),
        ]
    )
    # Works with both storage and YAML dashboards, without editing their resources.
    add_extra_js_url(hass, CARD_URL)
    add_extra_js_url(hass, SETTINGS_URL)
