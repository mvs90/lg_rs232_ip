"""Real websocket close timeout must not delay an already received LG result."""

import asyncio
from unittest.mock import AsyncMock

import aiohttp
from aiohttp import web as server_web
from yarl import URL
import pytest

from custom_components.lg_rs232_ip.web_manager import LGWebManager


@pytest.mark.parametrize("event", ["pictureDB", None])
async def test_unanswered_close_is_bounded_and_does_not_replay(event):
    requests = []
    done = asyncio.Event()

    async def handle(request):
        ws = server_web.WebSocketResponse(autoclose=False)
        await ws.prepare(request)
        await ws.send_str('0{"sid":"test"}')
        await ws.send_str("40")
        message = await ws.receive()
        requests.append(message.data)
        if event:
            await ws.send_str('42["pictureDB1",{"dynamicContrast":"low"}]')
        # Accept the closing frame, deliberately withhold the closing reply.
        await ws.receive()
        await done.wait()
        await ws.close()
        return ws

    app = server_web.Application()
    app.router.add_get("/socket.io/", handle)
    runner = server_web.AppRunner(app)
    await runner.setup()
    site = server_web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    client = LGWebManager("example.invalid", "test", "00" * 32)
    client._login = AsyncMock()
    client._session = aiohttp.ClientSession()
    port = site._server.sockets[0].getsockname()[1]
    client._url = lambda _, path: URL(f"http://127.0.0.1:{port}{path}")
    try:
        # Regression bound: the former aiohttp default waits 10 seconds here.
        result = await asyncio.wait_for(
            client._api("getPictureDBVal", event, keys=["dynamicContrast"]), timeout=1.5
        )
        assert result == ({"dynamicContrast": "low"} if event else None)
        assert len(requests) == 1
    finally:
        done.set()
        await client.async_close()
        await runner.cleanup()


@pytest.mark.parametrize('stall', ['headers', 'body'])
async def test_stalled_screenshot_retries_only_file_on_a_fresh_connection(monkeypatch, stall):
    from aiohttp.test_utils import TestServer
    from custom_components.lg_rs232_ip import web_manager

    monkeypatch.setattr(web_manager, '_CAPTURE_DOWNLOAD_TIMEOUT', aiohttp.ClientTimeout(total=.2, sock_read=.06))
    done = asyncio.Event()
    peers = []
    image = b'\xff\xd8\xffcomplete-dark-or-color-frame\xff\xd9'

    async def capture(request):
        assert request.path == '/tmp/capture123.jpg'
        assert request.headers['Connection'] == 'close'
        assert request.cookies['session'] == 'same-authenticated-session'
        peers.append(request.transport.get_extra_info('peername'))
        if len(peers) == 1:
            if stall == 'body':
                response = server_web.StreamResponse(headers={'Content-Length': str(len(image))})
                await response.prepare(request)
                await response.write(image[:4])
            await done.wait()
        return server_web.Response(body=image)

    app = server_web.Application()
    app.router.add_get('/tmp/capture123.jpg', capture)
    async with TestServer(app) as server:
        client = LGWebManager('example.invalid', 'test', verify_certificate=False)
        client._api = AsyncMock(return_value='/tmp/capture123.jpg')
        client._url = lambda _, path: URL(str(server.make_url(path)))
        client._session = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))
        client._session.cookie_jar.update_cookies({'session': 'same-authenticated-session'}, response_url=server.make_url('/'))
        try:
            assert await asyncio.wait_for(client.async_capture(), 1) == image
            assert len(peers) == 2 and peers[0] != peers[1]
            client._api.assert_awaited_once_with('capture', 'capture', height=720)
        finally:
            done.set()
            await client.async_close()
