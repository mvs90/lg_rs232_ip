"""Native HTTP/WebSocket boundary with real local sockets and cookie sessions."""

import asyncio
import json
from types import SimpleNamespace

from aiohttp import web
from aiohttp.test_utils import TestServer
import pytest
from yarl import URL

from custom_components.lg_rs232_ip.web_manager import LGWebError, LGWebManager


@pytest.fixture
async def native_server():
    state = SimpleNamespace(
        logins=0,
        commands=[],
        mode="ok",
        requested=asyncio.Event(),
        clients=[],
        redirects=0,
    )
    app = web.Application()

    async def status(request):
        return web.json_response({"status": 200, "data": "session" in request.cookies})

    async def challenge(request):
        return web.Response(text="challenge")

    async def challenge_text(request):
        return web.json_response({"status": 200, "data": {"text": "1234"}})

    async def login(request):
        state.logins += 1
        assert await request.json() == {
            "passwd": "private-test-password",
            "captcha": "1234",
        }
        response = web.json_response({"status": 200, "data": {"result": True}})
        response.set_cookie("session", str(state.logins))
        return response

    async def socket(request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        await ws.send_str('0{"sid":"test"}')
        await ws.send_str("40")
        incoming = await ws.receive_str()
        command = json.loads(incoming[2:])[1]["command"]
        state.commands.append((command, request.cookies.get("session")))
        state.requested.set()
        if state.mode == "expire":
            await ws.send_str('42["error",{"private":"not for diagnostics"}]')
        elif state.mode == "malformed":
            await ws.send_str("42not-json-private-test-password")
        elif state.mode == "oversized":
            await ws.send_str("x" * 262145)
        elif state.mode == "closed":
            await ws.close()
        elif state.mode == "reject":
            await ws.send_str('42["pictureDB1",{"returnValue":false}]')
        elif state.mode == "wrong_type":
            await ws.send_str('42["pictureDB1",[1,2,3]]')
        elif state.mode == "ok":
            await ws.send_str("2probe")
            assert await ws.receive_str() == "3probe"
            await ws.send_str('42["pictureDB99",{"dynamicContrast":"stale"}]')
            await ws.send_str('42["pictureDB1",{"dynamicContrast":"low"}]')
        async for _ in ws:
            pass
        return ws

    app.router.add_get("/login/checkLoginStatus", status)
    app.router.add_get("/login/captcha", challenge)
    app.router.add_get("/login/captchaText", challenge_text)
    app.router.add_post("/login/login", login)
    app.router.add_get("/socket.io/", socket)

    async def payload(request):
        if request.query.get("case") == "redirect":
            raise web.HTTPFound("/unexpected")
        if request.query.get("case") == "large":
            return web.Response(body=b"a" * 262145)
        return web.Response(text=request.query.get("case", "{}"))

    async def redirected(request):
        state.redirects += 1
        return web.Response(text="should not be reached")

    app.router.add_get("/payload", payload)
    app.router.add_get("/unexpected", redirected)
    async with TestServer(app) as server:

        def client():
            instance = LGWebManager(
                "test.invalid", "private-test-password", verify_certificate=False
            )
            instance._url = lambda _, path: URL(str(server.make_url(path)))
            state.clients.append(instance)
            return instance

        state.client = client
        state.server = server
        try:
            yield state
        finally:
            for instance in state.clients:
                await instance.async_close()


async def test_cookie_sessions_are_private_reused_and_closed(native_server):
    server = native_server
    first, second = server.client(), server.client()
    assert await first.async_get_picture_options() == {"dynamicContrast": "low"}
    assert await first.async_get_picture_options() == {"dynamicContrast": "low"}
    assert await second.async_get_picture_options() == {"dynamicContrast": "low"}
    assert server.logins == 2
    assert [x[1] for x in server.commands] == ["1", "1", "2"]
    await first.async_close()
    assert first._session is None and not first._authenticated
    assert await second.async_get_picture_options() == {"dynamicContrast": "low"}
    assert server.logins == 2


@pytest.mark.parametrize(
    "mode", ["expire", "malformed", "oversized", "closed", "reject", "wrong_type"]
)
async def test_bad_reply_never_replays_and_next_explicit_request_can_recover(
    native_server, mode
):
    server = native_server
    client = server.client()
    server.mode = mode
    with pytest.raises(LGWebError) as error:
        await client._api("testWrite", "pictureDB")
    assert "private-test-password" not in str(error.value)
    assert "not for diagnostics" not in str(error.value)
    assert [x[0] for x in server.commands] == ["testWrite"]
    server.mode = "ok"
    assert await client.async_get_picture_options() == {"dynamicContrast": "low"}
    assert len(server.commands) == 2
    assert server.logins == (2 if mode == "expire" else 1)


@pytest.mark.parametrize(
    "case",
    [
        "redirect",
        "large",
        "[]",
        "null",
        "not json",
        '{"status":401,"data":"private-test-password"}',
    ],
)
async def test_http_rejects_redirect_oversize_and_invalid_shapes(native_server, case):
    client = native_server.client()
    # Preserve the real response reader; only select the local fixture payload.
    original_url = client._url
    client._url = lambda port, path: original_url(port, path).with_query(case=case)
    with pytest.raises(LGWebError) as error:
        await client._json("GET", "/payload")
    assert native_server.redirects == 0
    assert "private-test-password" not in str(error.value)


async def test_cancellation_releases_web_priority_lock_and_connection(native_server):
    server = native_server
    client = server.client()
    server.mode = "stall"
    task = asyncio.create_task(client.async_get_picture_options())
    await asyncio.wait_for(server.requested.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not client._lock.locked()
    server.mode = "ok"
    assert await asyncio.wait_for(client.async_get_picture_options(), 1) == {
        "dynamicContrast": "low"
    }
    assert len(server.commands) == 2
