"""Serve the bundled dashboard card through Home Assistant's frontend."""

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig

CARD_VERSION = "2.1.0"
CARD_PATH = "/lg_rs232_ip/lg-display-remote.js"
CARD_URL = f"{CARD_PATH}?v={CARD_VERSION}"


async def async_register_card(hass):
    """Called once by integration setup, independent of the number of displays."""
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                CARD_PATH,
                str(Path(__file__).parent / "www" / "lg-display-remote.js"),
                False,
            )
        ]
    )
    # Works with both storage and YAML dashboards, without editing their resources.
    add_extra_js_url(hass, CARD_URL)
