"""Bounded, on-demand SCAP diagnostics from the paired foreground app."""

import asyncio
import math
import secrets

from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util


def number(value, low, high):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (ValueError, TypeError):
        return None
    return value if math.isfinite(value) and low <= value <= high else None


class PlatformDiagnostics:
    def __init__(self, manager):
        self.manager = manager
        self.ticket = None
        self.future = None
        self.data = {}
        self._cpu = None
        self._lock = asyncio.Lock()

    async def refresh(self):
        return await self._request("diagnostics")

    async def configure_wall(self, settings):
        return await self._request("video_wall", settings)

    async def _request(self, operation, settings=None):
        async with self._lock:
            if not self.manager.resident_connected:
                raise HomeAssistantError("Connect the resident display app first")
            self.ticket = {"id": secrets.token_hex(16), "operation": operation}
            if settings is not None:
                self.ticket["settings"] = settings
            self.future = asyncio.get_running_loop().create_future()
            self.manager.changed()
            try:
                result = await asyncio.wait_for(asyncio.shield(self.future), 25)
                if operation == "video_wall" and result.get("ok") is not True:
                    recovery = (
                        "previous settings restored"
                        if result.get("restored")
                        else "read the device settings before retrying"
                    )
                    raise HomeAssistantError(
                        "Video wall change failed ("
                        + result.get("reason", "unknown")
                        + "); "
                        + recovery
                    )
                return result
            except TimeoutError:
                raise HomeAssistantError("Display diagnostics timed out") from None
            finally:
                if not self.future.done():
                    self.future.cancel()
                self.ticket = self.future = None
                self.manager.changed()

    def accept(self, value):
        if (
            not self.ticket
            or value.get("id") != self.ticket["id"]
            or not self.future
            or self.future.done()
        ):
            raise ValueError
        result = value.get("result")
        if not isinstance(result, dict):
            raise ValueError
        if self.ticket["operation"] == "video_wall":
            self.future.set_result(
                {
                    "ok": result.get("ok") is True,
                    "restored": result.get("restored") is True,
                    "reason": result.get("reason")
                    if result.get("reason")
                    in {
                        "unavailable",
                        "invalid_readback",
                        "invalid_geometry",
                        "verification_failed",
                        "native_rejected",
                    }
                    else "unknown",
                }
            )
            return
        data = {"sampled_at": dt_util.utcnow().isoformat()}
        usage = result.get("usage", {})
        sensors = result.get("sensors", {})
        tile = result.get("tile", {})
        for name, raw in (("usage", usage), ("sensors", sensors), ("tile", tile)):
            data[name + "_available"] = (
                isinstance(raw, dict) and raw.get("returnValue") is True
            )
        if data["usage_available"]:
            memory = usage.get("memory", {})
            if isinstance(memory, dict):
                data["memory_bytes"] = {
                    key: int(val)
                    for key in ("total", "used", "free", "buffer", "cached")
                    if (val := number(memory.get(key), 0, 128 * 1024**3)) is not None
                }
            cpus = usage.get("cpus")
            current = []
            if isinstance(cpus, list) and 0 < len(cpus) <= 32:
                for cpu in cpus:
                    times = cpu.get("times", {}) if isinstance(cpu, dict) else {}
                    vals = [
                        number(times.get(k), 0, 10**16)
                        for k in ("user", "nice", "sys", "idle", "irq")
                    ]
                    if any(v is None for v in vals):
                        current = []
                        break
                    current.append((sum(vals), vals[3]))
            if current and self._cpu and len(current) == len(self._cpu):
                deltas = [
                    (new[0] - old[0], new[1] - old[1])
                    for new, old in zip(current, self._cpu)
                ]
                total = sum(d[0] for d in deltas)
                if total > 0 and all(0 <= idle <= elapsed for elapsed, idle in deltas):
                    data["cpu_percent"] = round(
                        100 * (1 - sum(d[1] for d in deltas) / total), 1
                    )
            self._cpu = current or None
        else:
            self._cpu = None
        if data["sensors_available"]:
            for name, low, high in (
                ("temperature", -50, 150),
                ("backlight", 0, 100),
                ("illuminance", 0, 200000),
                ("humidity", 0, 100),
                ("rotation", 0, 360),
            ):
                if (value := number(sensors.get(name), low, high)) is not None:
                    data[name] = value
            data["unsupported_sensors"] = [
                key
                for key in (
                    "temperature",
                    "backlight",
                    "illuminance",
                    "humidity",
                    "rotation",
                    "fan",
                    "checkscreen",
                )
                if sensors.get(key) == "Unsupported or Error"
            ]
        if data["tile_available"] and type(tile.get("enabled")) is bool:
            data["video_wall"] = {
                "enabled": tile["enabled"],
                "natural_mode": tile.get("naturalMode") is True,
            }
            for key in ("row", "column", "tileId"):
                if (
                    value := number(tile.get(key), 1, 225)
                ) is not None and value.is_integer():
                    data["video_wall"][key] = int(value)
        self.data = data
        self.future.set_result(data)
        self.manager._notify()

    def close(self):
        if self.future and not self.future.done():
            self.future.cancel()
