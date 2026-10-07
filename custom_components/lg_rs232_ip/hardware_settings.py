"""Verified serial audio and RGB calibration, independent of the optional app."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import SOUND_MODES
from .maintenance import integer
from .picture_settings import PictureSettingEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class HardwareSetting:
    command: str
    maximum: int = 254
    parameter: int | None = None
    options: dict | None = None


HARDWARE_SETTINGS = {
    "sound_mode": HardwareSetting("dy", options=SOUND_MODES),
    "audio_out": HardwareSetting(
        "sn", parameter=0xAA, options={"off": 0, "variable": 1, "fixed": 2}
    ),
    "digital_audio_input": HardwareSetting(
        "sn", parameter=0xA2, options={"digital": 0, "analog": 1}
    ),
    "audio_balance": HardwareSetting("kt", maximum=100),
    **{
        f"white_balance_{colour}_gain": HardwareSetting(command)
        for colour, command in zip(
            ("red", "green", "blue"), ("jm", "jn", "jo"), strict=True
        )
    },
    **{
        f"white_balance_{colour}_offset": HardwareSetting(command, maximum=127)
        for colour, command in zip(
            ("red", "green", "blue"), ("sx", "sy", "sz"), strict=True
        )
    },
}


class HardwareSettings(DataUpdateCoordinator):
    def __init__(self, hass, entry, display, controller):
        super().__init__(
            hass,
            _LOGGER,
            name="LG audio and white balance",
            update_interval=timedelta(seconds=60),
            config_entry=entry,
            always_update=False,
        )
        self.entry, self.display, self.controller = entry, display, controller
        self.awake = False
        self._settings_lock = asyncio.Lock()

    async def _read_one(self, key):
        spec = HARDWARE_SETTINGS[key]
        if spec.parameter is None:
            value = await self.display.async_send_command(
                *spec.command, 0xFF, use_cache=False
            )
        else:
            value = await self.display.async_get_subcommand(
                spec.command, spec.parameter, use_cache=False
            )
        if not isinstance(value, int) or isinstance(value, bool):
            return None
        if spec.options:
            return next((k for k, v in spec.options.items() if value == v), None)
        return value if 0 <= value <= spec.maximum else None

    async def _async_update_data(self):
        async with self._settings_lock:
            power = await self.display.async_get_power_status()
            if self.display.is_intentionally_unpowered or power is False:
                self.awake = False
                return {}
            if power is not True:
                self.awake = False
                raise UpdateFailed("Cannot read LG power state")
            self.awake = True
            result = {}
            for key in HARDWARE_SETTINGS:
                if (value := await self._read_one(key)) is not None:
                    result[key] = value
            return result

    async def async_set(self, key, value):
        spec = HARDWARE_SETTINGS.get(key)
        try:
            if spec is None:
                raise ValueError("Unknown LG hardware setting")
            if spec.options:
                if not isinstance(value, str) or value not in spec.options:
                    raise ValueError("Unsupported LG option")
                code = spec.options[value]
            else:
                value = code = integer(value, 0, spec.maximum)
        except (ValueError, TypeError, OverflowError) as err:
            raise HomeAssistantError(str(err)) from None
        async with self._settings_lock, self.controller._control_lock:
            if (
                self.display.is_intentionally_unpowered
                or await self.display.async_get_power_status(use_cache=False)
                is not True
            ):
                self.awake = False
                raise HomeAssistantError(
                    "Display must be on to change audio/calibration"
                )
            self.awake = True
            before = await self._read_one(key)
            if before is None:
                raise HomeAssistantError(
                    "Setting is unavailable in the current LG mode/input"
                )
            actual = before
            if actual != value:
                if spec.parameter is None:
                    await self.display.async_send_command(*spec.command, code)
                else:
                    await self.display.async_send_raw_command(
                        *spec.command,
                        spec.parameter,
                        query_suffix=f" {code:02x}",
                        use_cache=False,
                    )
                # Do not replay a mutation, including when its ACK was lost.
                for attempt in range(3):
                    actual = await self._read_one(key)
                    if actual == value:
                        break
                    if attempt < 2:
                        await asyncio.sleep(0.25)
            data = dict(self.data or {})
            if actual is None:
                data.pop(key, None)
            else:
                data[key] = actual
            self.async_set_updated_data(data)
            if actual != value:
                raise HomeAssistantError(
                    "Display did not confirm the requested audio/calibration value"
                )


class HardwareSettingEntity(PictureSettingEntity):
    """Use the same identity/availability rules as other advanced controls."""

    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)
        self._attr_icon = (
            "mdi:palette" if key.startswith("white_balance_") else "mdi:volume-high"
        )
