"""Test the observed vendor protocol without a physical panel or credentials."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import aiohttp
import pytest
from custom_components.lg_rs232_ip.web_manager import (
    LGWebError,
    LGWebManager,
    normalize_fingerprint,
)


@pytest.fixture
def web():
    return LGWebManager("example.test", "test-password", "ab" * 32)


@pytest.mark.parametrize("value", ["", "ab" * 31, "zz" * 32])
def test_rejects_invalid_certificate_pin(value):
    with pytest.raises(ValueError):
        normalize_fingerprint(value)


def test_fingerprint_accepts_browser_colon_format():
    assert normalize_fingerprint(":".join(["AB"] * 32)) == "ab" * 32


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data", [b"GIF89a", b"", b"\x89PNG\r\n\x1a\n" + b"x" * (5 * 1024 * 1024)]
)
async def test_invalid_images_rejected_before_network(web, data):
    web._login = AsyncMock()
    with pytest.raises(LGWebError):
        await web.async_upload_image(data)
    web._login.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_validates_returned_path_and_only_deletes_owned_asset(web):
    web._login = AsyncMock()

    async def request(method, path, **kwargs):
        if method == "POST":
            form = kwargs["data"]
            name = form._fields[0][0]["filename"]
            return {
                "result": True,
                "data": {
                    "files": {"file": {"path": "/mnt/lg/appstore/signage/" + name}}
                },
            }
        return {"payload": {"returnValue": True}}

    web._json = AsyncMock(side_effect=request)
    asset = await web.async_upload_image(b"\x89PNG\r\n\x1a\ncontent")
    await web.async_delete_image(asset)
    assert web._json.await_args.kwargs["params"]["path"][0]["itemPath"] == asset["path"]
    for bad in [
        {"name": "existing.png", "path": "/mnt/lg/appstore/signage/existing.png"},
        {**asset, "path": "/etc/passwd"},
    ]:
        with pytest.raises(LGWebError, match="non-owned"):
            await web.async_delete_image(bad)


@pytest.mark.asyncio
async def test_upload_rejects_unexpected_storage(web):
    web._login = AsyncMock()
    web._json = AsyncMock(
        return_value={
            "result": True,
            "data": {"files": {"file": {"path": "/other/location"}}},
        }
    )
    with pytest.raises(LGWebError, match="unexpected"):
        await web.async_upload_image(b"\xff\xd8\xffjpeg")


@pytest.mark.asyncio
async def test_toast_socket_handshake_event_and_certificate_pin(web):
    web._login = AsyncMock()
    ws = AsyncMock()
    ws.receive.side_effect = [
        SimpleNamespace(type=aiohttp.WSMsgType.TEXT, data=p)
        for p in [
            '0{"sid":"test"}',
            "40",
            "2",
            '42["unrelated",{}]',
            '42["return",{"from":"toast","result":true}]',
        ]
    ]
    context = AsyncMock()
    context.__aenter__.return_value = ws
    web._session = Mock()
    web._session.ws_connect.return_value = context
    await web.async_toast("Hello")
    assert web._session.ws_connect.call_args.kwargs["ssl"] is web._ssl
    assert ws.send_str.await_args_list[-1].args == ("3",)
    event = json.loads(ws.send_str.await_args_list[0].args[0][2:])
    assert event[1]["command"] == "sendToast"
    assert event[1]["message"] == "Hello"
    assert "test-password" not in repr(event)


@pytest.mark.asyncio
async def test_login_rejected_and_error_sanitized(web):
    web._session = Mock()
    response = AsyncMock(status=200)
    response.content.iter_chunked = lambda _: async_chunks([b"svg"])
    context = AsyncMock()
    context.__aenter__.return_value = response
    web._session.get.return_value = context
    web._json = AsyncMock(side_effect=[{"text": "1234"}, {"result": False}])
    with pytest.raises(LGWebError) as err:
        await web._login()
    assert "test-password" not in str(err.value)
    assert not web._authenticated
    assert web._json.await_args.kwargs["body"] == {
        "passwd": "test-password",
        "captcha": "1234",
    }


@pytest.mark.asyncio
async def test_transport_failure_is_not_replayed_and_is_sanitized(web):
    web._session = Mock()
    web._session.request.side_effect = aiohttp.ClientError("private-cookie-and-url")
    with pytest.raises(LGWebError) as err:
        await web._json("POST", "/file/contentManager")
    assert "private" not in str(err.value)
    assert web._session.request.call_count == 1
    assert web._session.request.call_args.kwargs["allow_redirects"] is False


async def async_chunks(chunks):
    for chunk in chunks:
        yield chunk


@pytest.mark.asyncio
async def test_json_response_can_be_fragmented_and_is_bounded(web):
    web._session = Mock()
    context = AsyncMock()
    response = Mock(status=200)
    response.content.iter_chunked = lambda _: async_chunks(
        [b'{"status":200,', b'"data":true}']
    )
    context.__aenter__.return_value = response
    web._session.request.return_value = context
    assert await web._json("GET", "/login/checkLoginStatus") is True
    response.content.iter_chunked = lambda _: async_chunks([b"x" * 262145])
    with pytest.raises(LGWebError, match="size limit"):
        await web._json("GET", "/login/checkLoginStatus")


@pytest.mark.asyncio
async def test_capture_download_uses_control_port_pin_and_no_redirects(web):
    web._api = AsyncMock(return_value="/tmp/capture12345.jpg")
    image = b"\xff\xd8\xffjpeg\xff\xd9"
    response = Mock(status=200)
    response.content.iter_chunked = lambda _: async_chunks([image[:4], image[4:]])
    context = AsyncMock()
    context.__aenter__.return_value = response
    web._session = Mock()
    web._session.get.return_value = context
    assert await web.async_capture() == image
    url = web._session.get.call_args.args[0]
    assert url.port == 3737
    assert url.path == "/tmp/capture12345.jpg"
    assert web._session.get.call_args.kwargs == {
        "ssl": web._ssl,
        "allow_redirects": False,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "https://other.test/image.jpg",
        "/tmp/../private.jpg",
        "/tmp/capture123.jpg?secret=1",
        "",
        {"returnValue": False},
    ],
)
async def test_capture_path_cannot_escape_device_or_read_arbitrary_file(web, path):
    web._api = AsyncMock(return_value=path)
    web._session = Mock()
    with pytest.raises(LGWebError, match="capture path"):
        await web.async_capture()
    web._session.get.assert_not_called()


@pytest.mark.asyncio
async def test_capture_rejects_html_login_page(web):
    web._api = AsyncMock(return_value="/tmp/capture123.jpg")
    response = Mock(status=200)
    response.content.iter_chunked = lambda _: async_chunks([b"<html>Login</html>"])
    context = AsyncMock()
    context.__aenter__.return_value = response
    web._session = Mock()
    web._session.get.return_value = context
    with pytest.raises(LGWebError, match="invalid JPEG"):
        await web.async_capture()
