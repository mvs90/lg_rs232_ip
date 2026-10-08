import asyncio
from unittest.mock import AsyncMock
import pytest
from custom_components.lg_rs232_ip.lg_display import LGDisplay


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("v 01 OK0200x", False),
        ("v 01 OK0201x", True),
        ("v 01 NG02x", None),
        ("v 01 OK02x", None),
        ("v 01 OK0202x", None),
        (None, None),
    ],
)
async def test_signal_decoding(reply, expected):
    display = LGDisplay("example.invalid")
    display.async_send_raw_command = AsyncMock(return_value=reply)
    assert await display.async_get_signal_status() is expected
    display.async_send_raw_command.assert_awaited_once_with(
        "s", "v", 2, query_suffix=" ff", use_cache=False
    )


@pytest.mark.asyncio
async def test_fragmented_reply_and_wrong_command_are_not_accepted():
    commands = []

    async def handle(reader, writer):
        try:
            while data := await reader.readuntil(b"\r"):
                if data == b"\r":
                    continue
                commands.append(data)
                writer.write(b"f 01 OK32xa 02 OK01xa 01 OK")
                await writer.drain()
                await asyncio.sleep(0.01)
                writer.write(b"00x")
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    display = LGDisplay("127.0.0.1", server.sockets[0].getsockname()[1])
    try:
        assert await display.async_get_power_status(use_cache=False) is False
        assert commands == [b"ka 01 ff\r"]
    finally:
        await display.async_disconnect()
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_bad_power_value_is_unknown():
    display = LGDisplay("example.invalid")
    display.async_send_command = AsyncMock(return_value=2)
    assert await display.async_get_power_status() is None
    assert not await display.async_power_off()
    assert not await display.async_power_on()


@pytest.mark.asyncio
async def test_shared_query_cache_and_write_invalidation():
    from unittest.mock import Mock

    display = LGDisplay("example.invalid")
    reader = asyncio.StreamReader()
    writer = Mock()
    writer.drain = AsyncMock()

    def reply(data):
        reader.feed_data(b"f 01 OK32x")

    writer.write.side_effect = reply
    display._reader, display._writer, display._connected = reader, writer, True
    assert await display.async_get_volume() == 50
    assert await display.async_get_volume() == 50
    assert writer.write.call_count == 1
    await display.async_set_volume(50)
    await display.async_get_volume()
    assert writer.write.call_count == 3


@pytest.mark.asyncio
async def test_cancelled_query_discards_connection():
    from unittest.mock import Mock

    display = LGDisplay("example.invalid")
    display._reader = asyncio.StreamReader()
    writer = Mock()
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()
    display._writer = writer
    display._connected = True
    task = asyncio.create_task(display.async_get_volume())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    writer.close.assert_called_once()
    assert not display.is_connected


@pytest.mark.asyncio
async def test_rejected_optional_query_is_temporarily_suppressed():
    from unittest.mock import Mock

    display = LGDisplay("example.invalid")
    reader = asyncio.StreamReader()
    writer = Mock()
    writer.drain = AsyncMock()
    writer.write.side_effect = lambda _: reader.feed_data(b"g 01 NGffx")
    display._reader, display._writer, display._connected = reader, writer, True
    assert await display.async_send_command("n", "g", 255) is None
    assert await display.async_send_command("n", "g", 255) is None
    assert writer.write.call_count == 1


@pytest.mark.asyncio
async def test_x_command_letter_is_not_the_frame_terminator():
    from unittest.mock import Mock

    display = LGDisplay("example.invalid")
    reader = asyncio.StreamReader()
    writer = Mock()
    writer.drain = AsyncMock()
    loop = asyncio.get_running_loop()

    def reply(data):
        reader.feed_data(b"x")
        loop.call_soon(reader.feed_data, b" 01 OK01x")

    writer.write.side_effect = reply
    display._reader, display._writer, display._connected = reader, writer, True
    assert await display.async_get_picture_mode() == 1
    writer.write.assert_called_once_with(b"dx 01 ff\r")


@pytest.mark.parametrize("retry", ["foreground", "expired"])
async def test_silent_optional_background_query_backs_off_but_can_recover(monkeypatch, retry):
    import time
    from unittest.mock import Mock
    from custom_components.lg_rs232_ip import lg_display as module

    display = LGDisplay("example.invalid")
    writer = Mock(drain=AsyncMock(), wait_closed=AsyncMock())
    display._reader = asyncio.StreamReader()
    display._writer, display._connected = writer, True
    monkeypatch.setattr(module, "COMMAND_TIMEOUT", .01)
    assert await display.async_get_subcommand("sn", 0xC4, background_query=True) is None
    assert not display.is_connected
    assert await display.async_get_subcommand("sn", 0xC4, background_query=True) is None
    writer.write.assert_called_once()
    # Mode changes must not immediately repeat a command that timed out.
    display._picture_settings_changed()
    assert await display.async_get_subcommand("sn", 0xC4, background_query=True) is None
    reader = asyncio.StreamReader()
    writer.write.side_effect = lambda _: reader.feed_data(b"n 01 OKc401x")
    display._reader, display._writer, display._connected = reader, writer, True
    if retry == "expired":
        display._query_retry_after[("s", "n", 0xC4, " ff")] = time.monotonic() - 1
    assert await display.async_get_subcommand("sn", 0xC4, background_query=retry == "expired") == 1
    assert display._query_retry_after == {}
