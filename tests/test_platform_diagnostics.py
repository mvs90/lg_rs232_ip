"""Realistic SCAP values: no synthetic zeros, request scoping and counter resets."""

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.lg_rs232_ip.platform_diagnostics import PlatformDiagnostics
from custom_components.display_studio.layout_config import validate_multicast_url


def platform():
    return PlatformDiagnostics(
        SimpleNamespace(resident_connected=True, changed=Mock(), _notify=Mock())
    )


async def sample(p, result):
    task = asyncio.create_task(p.refresh())
    await asyncio.sleep(0)
    p.accept({"id": p.ticket["id"], "result": result})
    return await task


def usage(idle, user):
    return {
        "returnValue": True,
        "memory": {
            "total": 2000000,
            "used": 1000000,
            "free": 100000,
            "private": "secret",
        },
        "cpus": [
            {"times": {"user": user, "nice": 0, "sys": 0, "idle": idle, "irq": 0}}
        ],
    }


async def test_diagnostics_counter_deltas_missing_sensors_and_reboot():
    p = platform()
    result = await sample(
        p,
        {
            "usage": usage(1000, 100),
            "sensors": {
                "returnValue": True,
                "temperature": 36,
                "backlight": "75",
                "humidity": "Unsupported or Error",
                "illuminance": "Unsupported or Error",
            },
            "tile": {
                "returnValue": True,
                "enabled": False,
                "row": 15,
                "column": 15,
                "tileId": 6,
                "naturalMode": True,
            },
        },
    )
    assert result["temperature"] == 36 and result["backlight"] == 75
    assert "humidity" not in result and "illuminance" not in result
    assert "humidity" in result["unsupported_sensors"]
    assert "private" not in result["memory_bytes"]
    assert "cpu_percent" not in result
    assert (await sample(p, {"usage": usage(1080, 120)}))["cpu_percent"] == 20
    assert "cpu_percent" not in await sample(p, {"usage": usage(10, 1)})
    assert (
        "temperature" not in p.data
    )  # unavailable samples cannot retain a stale value


async def test_ticket_scope_cancellation_and_disconnection():
    p = platform()
    with pytest.raises(ValueError):
        p.accept({"id": "unsolicited", "result": {}})
    task = asyncio.create_task(p.refresh())
    await asyncio.sleep(0)
    with pytest.raises(ValueError):
        p.accept({"id": "wrong", "result": {}})
    p.close()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert p.ticket is None
    p.manager.resident_connected = False
    with pytest.raises(HomeAssistantError):
        await p.refresh()


async def test_wall_failure_reports_verified_rollback():
    p = platform()
    task = asyncio.create_task(p.configure_wall({"enabled": False}))
    await asyncio.sleep(0)
    assert p.ticket["operation"] == "video_wall"
    p.accept({"id": p.ticket["id"], "result": {"ok": False, "restored": True}})
    with pytest.raises(HomeAssistantError, match="previous settings restored"):
        await task


@pytest.mark.parametrize(
    "value",
    [
        "udp://192.168.1.2:5000",
        "udp://224.0.0.1:5000",
        "udp://239.1.2.3:0",
        "udp://239.1.2.3:65536",
        "udp://user@239.1.2.3:5000",
        "udp://239.1.2.3:5000/?x=1",
        "http://239.1.2.3:5000",
        "udp://239.1.2.3:5000\n",
        None,
        {},
        "",
    ],
)
def test_multicast_rejects_unicast_credentials_special_groups_and_invalid_urls(value):
    with pytest.raises(ValueError):
        validate_multicast_url(value, required=True)


def test_multicast_canonical_local_group():
    assert (
        validate_multicast_url("udp://239.255.20.35:15000")
        == "udp://239.255.20.35:15000"
    )
    assert validate_multicast_url("") == ""
