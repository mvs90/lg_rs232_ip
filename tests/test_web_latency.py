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
