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
        login_status_peers=[],
    )
    app = web.Application()

    async def status(request):
        state.login_status_peers.append(request.transport.get_extra_info('peername'))
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
        if state.mode == "handshake_reject":
            await ws.send_str('44{"message":"session expired"}')
            await ws.close()
            return ws
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


async def test_rejected_handshake_invalidates_cached_login_without_replaying(native_server):
    server = native_server
    client = server.client()
    server.mode = "handshake_reject"
    with pytest.raises(LGWebError, match="login rejected"):
        await client._api("testWrite", "pictureDB")
    assert not client._authenticated
    assert server.commands == []
    server.mode = "ok"
    assert await client.async_get_picture_options() == {"dynamicContrast": "low"}
    assert server.logins == 2
    assert [command for command, _ in server.commands] == ["getPictureDBVal"]


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


async def test_concurrent_capture_and_control_share_one_login(native_server):
    server = native_server
    client = server.client()
    # Independent read requests use separate WebSockets but the same cookie.
    results = await asyncio.gather(
        client.async_get_picture_options(),
        client._api('getPictureDBVal', 'pictureDB'),
    )
    assert results == [{'dynamicContrast': 'low'}] * 2
    assert server.logins == 1
    assert [cookie for _, cookie in server.commands] == ['1', '1']


async def test_periodic_login_check_does_not_reuse_an_idle_http_socket(native_server):
    server = native_server
    client = server.client()
    await client._login()
    client._login_checked_at = 0
    await client._login()
    assert server.logins == 1, 'Refreshing the status must preserve the authenticated cookie'
    assert len(server.login_status_peers) == 2
    assert server.login_status_peers[0] != server.login_status_peers[1]


@pytest.fixture
async def capture_server():
    state = SimpleNamespace(connections=0, commands=[], pings=0, mode='ok', requested=asyncio.Event())
    app = web.Application()

    async def socket(request):
        state.connections += 1
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        await ws.send_str('0{"sid":"capture","pingInterval":100}')
        await ws.send_str('40')
        async for incoming in ws:
            if incoming.type != web.WSMsgType.TEXT:
                continue
            if incoming.data == '2':
                state.pings += 1
                await ws.send_str('3')
                continue
            if not incoming.data.startswith('42'):
                continue
            command = json.loads(incoming.data[2:])[1]
            state.commands.append(command)
            state.requested.set()
            if state.mode == 'close_once':
                state.mode = 'ok'
                await ws.close()
                break
            if state.mode == 'expire':
                await ws.send_str('42["error",{"private":"secret"}]')
                continue
            if state.mode == 'stall':
                continue
            if state.mode == 'malformed':
                await ws.send_str('42invalid')
                continue
            event_id = command['eventID']
            await ws.send_str('42' + json.dumps(['capture' + str(event_id - 1), '/tmp/capture999.jpg']))
            await ws.send_str('42' + json.dumps(['capture' + str(event_id), '/tmp/capture' + str(event_id) + '.jpg']))
        return ws

    app.router.add_get('/socket.io/', socket)
    async with TestServer(app) as server:
        import aiohttp
        client = LGWebManager('test.invalid', 'secret', verify_certificate=False)
        client._url = lambda _, path: URL(str(server.make_url(path)))
        client._session = aiohttp.ClientSession()
        client._authenticated = True
        import time
        client._login_checked_at = time.monotonic()
        state.client = client
        try:
            yield state
        finally:
            await client.async_close()


async def test_capture_channel_reuses_connection_and_rejects_old_frame_ids(capture_server):
    server = capture_server
    for i in range(1, 101):
        assert await server.client._api('capture', 'capture', height=720) == f'/tmp/capture{i}.jpg'
    assert server.connections == 1
    assert len(server.commands) == 100
    assert all(item['height'] == 720 for item in server.commands)
    ws = server.client._capture_socket
    await server.client.async_close()
    assert ws.closed and server.client._capture_socket is None


async def test_capture_channel_services_engineio_client_ping(capture_server):
    server = capture_server
    await server.client._api('capture', 'capture', height=720)
    server.client._capture_ping_at -= 1
    await server.client._api('capture', 'capture', height=720)
    assert server.pings == 1 and server.connections == 1


async def test_capture_channel_reconnects_once_after_transport_loss(capture_server):
    server = capture_server
    server.mode = 'close_once'
    assert await server.client._api('capture', 'capture', height=720) == '/tmp/capture2.jpg'
    assert server.connections == 2


async def test_capture_channel_discards_socket_after_idle(capture_server):
    server = capture_server
    await server.client._api('capture', 'capture', height=720)
    first = server.client._capture_socket
    server.client._capture_used_at -= 30
    await server.client._api('capture', 'capture', height=720)
    assert server.connections == 2 and first.closed


@pytest.mark.parametrize('mode', ['expire', 'malformed'])
async def test_capture_channel_never_replays_auth_or_invalid_response(capture_server, mode):
    server = capture_server
    server.mode = mode
    with pytest.raises(LGWebError):
        await server.client._api('capture', 'capture', height=720)
    assert server.connections == 1 and len(server.commands) == 1
    assert server.client._capture_socket is None
    if mode == 'expire':
        assert not server.client._authenticated


async def test_capture_channel_cancellation_closes_socket_and_next_request_recovers(capture_server):
    server = capture_server
    server.mode = 'stall'
    task = asyncio.create_task(server.client._api('capture', 'capture', height=720))
    await asyncio.wait_for(server.requested.wait(), 1)
    ws = server.client._capture_socket
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert ws.closed and server.client._capture_socket is None
    server.mode = 'ok'
    assert await server.client._api('capture', 'capture', height=720) == '/tmp/capture2.jpg'
