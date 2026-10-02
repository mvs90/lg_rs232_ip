"""The unauthenticated video page is token-bound, escaped and short-lived."""

from unittest.mock import patch

from aiohttp import web
import pytest

from custom_components.lg_rs232_ip.stream_page import StreamPageView


@pytest.mark.asyncio
async def test_stream_page_escapes_source_and_expires():
    view = StreamPageView()
    with patch(
        "custom_components.lg_rs232_ip.stream_page.time.monotonic", return_value=100
    ):
        token = view.add('https://example.test/video?x="<script>', 10, True)
        result = await view.get(None, token)
    assert len(token) >= 40
    assert "<script>" not in result.text
    assert "&quot;&lt;script&gt;" in result.text
    assert "muted " in result.text
    assert result.headers["Cache-Control"] == "no-store"
    with patch(
        "custom_components.lg_rs232_ip.stream_page.time.monotonic", return_value=231
    ):
        with pytest.raises(web.HTTPNotFound):
            await view.get(None, token)
    assert not view.pages


@pytest.mark.asyncio
async def test_stream_page_does_not_accept_unknown_tokens():
    with pytest.raises(web.HTTPNotFound):
        await StreamPageView().get(None, "guess")


@pytest.mark.asyncio
async def test_real_ha_view_serves_only_live_token_without_login(tmp_path):
    from aiohttp.test_utils import TestClient, TestServer
    from homeassistant.core import HomeAssistant

    hass = HomeAssistant(str(tmp_path))
    view = StreamPageView()
    app = web.Application()
    view.register(hass, app, app.router)
    token = view.add("http://media.test/live.m3u8", 30, True)
    async with TestClient(TestServer(app)) as client:
        response = await client.get(f"/api/lg_rs232_ip/stream/{token}")
        assert response.status == 200
        assert response.content_type == "text/html"
        assert "http://media.test/live.m3u8" in await response.text()
        view.pages.pop(token)
        response = await client.get(f"/api/lg_rs232_ip/stream/{token}")
        assert response.status == 404
    await hass.async_stop(force=True)
