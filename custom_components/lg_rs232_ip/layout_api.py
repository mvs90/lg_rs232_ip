"""Authenticated administrator editor API; the panel token cannot edit layouts."""

import json
from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .const import DOMAIN
from .layout_config import presets, validate_layout
from .layouts import LayoutConflict


def require_admin(request):
    user = request.get("hass_user")
    if not user or not user.is_admin:
        raise web.HTTPForbidden()


async def read_document(request):
    raw = bytearray()
    async for part in request.content.iter_chunked(8192):
        raw.extend(part)
        if len(raw) > 131072:
            raise web.HTTPRequestEntityTooLarge(max_size=131072, actual_size=len(raw))
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError
        return data
    except (ValueError, TypeError):
        raise web.HTTPBadRequest(text="Invalid layout document") from None


class LayoutValidateView(HomeAssistantView):
    url = "/api/lg_rs232_ip/layout_validate"
    name = "api:lg_rs232_ip:layout_validate"
    requires_auth = True

    async def post(self, request):
        require_admin(request)
        data = await read_document(request)
        try:
            config = validate_layout(data.get("config"))
        except (ValueError, TypeError, KeyError, AttributeError) as err:
            raise web.HTTPBadRequest(text=str(err)) from None
        return web.json_response(
            {"config": config}, headers={"Cache-Control": "no-store"}
        )


class LayoutListView(HomeAssistantView):
    url = "/api/lg_rs232_ip/layouts"
    name = "api:lg_rs232_ip:layouts"
    requires_auth = True

    def __init__(self, hass):
        self.hass = hass

    async def get(self, request):
        require_admin(request)
        entries = []
        for entry_id, data in self.hass.data.get(DOMAIN, {}).items():
            if not isinstance(data, dict) or "layouts" not in data:
                continue
            app = data.get("display_app")
            entries.append(
                {
                    "entry_id": entry_id,
                    "name": data.get("name", "LG Display"),
                    "app_enabled": bool(app and app.enabled),
                    "resident_enabled": bool(app and app.resident),
                    "connected": bool(app and app.resident_connected),
                }
            )
        return web.json_response(
            {"entries": entries, "presets": presets()},
            headers={"Cache-Control": "no-store"},
        )


class LayoutEditorView(HomeAssistantView):
    url = "/api/lg_rs232_ip/layout/{entry_id}"
    name = "api:lg_rs232_ip:layout"
    requires_auth = True

    def __init__(self, hass):
        self.hass = hass

    def manager(self, request, entry_id):
        require_admin(request)
        manager = self.hass.data.get(DOMAIN, {}).get(entry_id, {}).get("layouts")
        if not manager:
            raise web.HTTPNotFound()
        return manager

    async def get(self, request, entry_id):
        manager = self.manager(request, entry_id)
        return web.json_response(
            {
                **manager.document(),
                "values": manager.values(),
                "timezone": str(self.hass.config.time_zone),
            },
            headers={"Cache-Control": "no-store"},
        )

    async def post(self, request, entry_id):
        manager = self.manager(request, entry_id)
        data = await read_document(request)
        try:
            if not isinstance(data, dict) or type(data.get("revision")) is not int:
                raise ValueError("Supply the current layout revision")
            result = await manager.async_save(data.get("config"), data["revision"])
        except LayoutConflict as err:
            raise web.HTTPConflict(text=str(err)) from None
        except (ValueError, TypeError, KeyError, AttributeError) as err:
            raise web.HTTPBadRequest(text=str(err)) from None
        return web.json_response(result, headers={"Cache-Control": "no-store"})
