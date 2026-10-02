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
        "s", "v", 2, query_suffix=" ff"
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
