"""Short-lived, unguessable HTML video pages for the Signage browser."""

from __future__ import annotations

import html
import secrets
import time

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.network import get_url

from .const import DOMAIN


class StreamPageView(HomeAssistantView):
    url = "/api/lg_rs232_ip/stream/{token}"
    name = "api:lg_rs232_ip:stream"
    requires_auth = False

    def __init__(self):
        self.pages = {}

    def add(self, source, duration, muted):
        token = secrets.token_urlsafe(32)
        self.pages[token] = (time.monotonic() + duration + 120, source, muted)
        return token

    async def get(self, request, token):
        item = self.pages.get(token)
        if item is None or item[0] <= time.monotonic():
            self.pages.pop(token, None)
            raise web.HTTPNotFound()
        _, source, muted = item
        body = (
            '<!doctype html><html><head><meta name="referrer" content="no-referrer">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            "<title>Home Assistant video</title></head>"
            '<body style="margin:0;background:black;overflow:hidden">'
            "<video autoplay playsinline controls "
            + ("muted " if muted else "")
            + 'style="width:100vw;height:100vh" src="'
            + html.escape(source, quote=True)
            + '"></video></body></html>'
        )
        return web.Response(
            text=body,
            content_type="text/html",
            headers={
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'; media-src http: https:; style-src 'unsafe-inline'; frame-ancestors 'none'",
            },
        )


def create_stream_page(hass, source, duration, muted):
    """Register once per HA instance; content exists only for its presentation."""
    data = hass.data[DOMAIN]
    view = data.get("stream_page_view")
    if view is None:
        view = StreamPageView()
        hass.http.register_view(view)
        data["stream_page_view"] = view
    base = get_url(hass, prefer_external=False)
    token = view.add(source, duration, muted)
    return f"{base}/api/lg_rs232_ip/stream/{token}", lambda: view.pages.pop(token, None)
