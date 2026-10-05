"""Serve the bundled dashboard card through Home Assistant's frontend."""

from pathlib import Path

from homeassistant.components.frontend import (
    add_extra_js_url,
    async_register_built_in_panel,
)
from homeassistant.components.http import StaticPathConfig

CARD_VERSION = "2.11.0"
CARD_PATH = "/lg_rs232_ip/lg-display-remote.js"
CARD_URL = f"{CARD_PATH}?v={CARD_VERSION}"


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
            StaticPathConfig("/lg_rs232_ip/studio.js", str(root / "studio.js"), False),
            StaticPathConfig(
                "/lg_rs232_ip/studio.css", str(root / "studio.css"), False
            ),
            StaticPathConfig(
                "/lg_rs232_ip/layout-runtime.js",
                str(root / "display-app" / "layout.js"),
                False,
            ),
            StaticPathConfig(
                "/lg_rs232_ip/cards.js", str(root / "display-app" / "cards.js"), False
            ),
            StaticPathConfig(
                "/lg_rs232_ip/weather.js",
                str(root / "display-app" / "weather.js"),
                False,
            ),
            StaticPathConfig(
                "/lg_rs232_ip/layout.css",
                str(root / "display-app" / "layout.css"),
                False,
            ),
        ]
    )
    # Works with both storage and YAML dashboards, without editing their resources.
    add_extra_js_url(hass, CARD_URL)
    async_register_built_in_panel(
        hass,
        "custom",
        sidebar_title="LG Display Studio",
        sidebar_icon="mdi:monitor-edit",
        frontend_url_path="lg-display-studio",
        require_admin=True,
        config={
            "_panel_custom": {
                "name": "lg-display-studio",
                "embed_iframe": False,
                "trust_external": False,
                "module_url": f"/lg_rs232_ip/studio.js?v={CARD_VERSION}",
            }
        },
    )
