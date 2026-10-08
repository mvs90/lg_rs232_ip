"""Shared picture options with bounded reads and verified, non-replayed writes."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
import re

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed

from .command_queue import PriorityLock, interactive_command
from .const import DOMAIN, PICTURE_MODES
from .device_profile import is_uh5f, ok_payload
from .web_manager import LGWebError

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PictureOption:
    options: dict[str, int]
    parameter: int | None = None
    command: str = "sn"
    input_code: int | None = None


PICTURE_OPTIONS = {
    "gamma": PictureOption({"low": 0, "medium": 1, "high1": 2, "high2": 3}, 0xAD),
    "black_level": PictureOption({"low": 0, "high": 1, "auto": 2}, 0xAE),
    "hdr_picture_mode": PictureOption({"mall": 0, "general": 1, "corporate": 2, "education": 4}, 0xC4),
    "hdr_tone_mapping": PictureOption({"off": 0, "on": 1}, 0xC5),
    "hdmi_it_content": PictureOption({"off": 0, "on": 1}, 0x99),
    "brightness_schedule": PictureOption({"off": 0, "on": 1}, command="sm"),
    **{f"deep_color_hdmi{n}": PictureOption({"off": 0, "on": 1}, 0xAF, input_code=0x8F+n) for n in range(1, 4)},
    "min_backlight": PictureOption({str(v): v for v in range(0, 101, 5)}, 0xAB, input_code=0),
    "max_backlight": PictureOption({str(v): v for v in range(0, 101, 5)}, 0xAB, input_code=1),
}
NATIVE_OPTIONS = {
    "dynamic_contrast": ("dynamicContrast", ("off", "low", "medium", "high")),
    "dynamic_color": ("dynamicColor", ("off", "low", "medium", "high")),
    "super_resolution": ("superResolution", ("off", "low", "medium", "high")),
    "noise_reduction": ("noiseReduction", ("off", "low", "medium", "high", "auto")),
    "mpeg_noise_reduction": ("mpegNoiseReduction", ("off", "low", "medium", "high", "auto")),
    "color_gamut": ("colorGamut", ("auto", "extended")),
}
NATIVE_NUMBERS = {"skin_color": "skinColor", "sky_color": "skyColor", "grass_color": "grassColor"}
NATIVE_KEYS = [v[0] for v in NATIVE_OPTIONS.values()] + list(NATIVE_NUMBERS.values()) + [
    "pictureMode", "pictureModeSettingsActive", "pictureControlLimitation", "pictureSettingModified",
]
PICTURE_ACTIONS = {"picture_reset", "picture_apply_all_inputs"}


def native_options(values):
    """Do not offer dormant profile values when LG locks picture editing."""
    if not isinstance(values, dict) or values.get("pictureModeSettingsActive") not in (True, "true") or values.get("pictureControlLimitation") not in (False, "false"):
        return {}
    mode = values.get("pictureMode")
    if mode not in {"normal", "vivid", "govCorp", "sports", "game", "aps", "eco", "expert1"}:
        return {}
    result = {key: values[raw] for key, (raw, options) in NATIVE_OPTIONS.items() if values.get(raw) in options}
    for key, raw in NATIVE_NUMBERS.items():
        value = values.get(raw)
        if not isinstance(value, bool):
            try:
                number = int(value)
                if number == float(value) and -5 <= number <= 5:
                    result[key] = str(number)
            except (ValueError, TypeError, OverflowError):
                pass
    if mode == "expert1":
        result.pop("dynamic_color", None)
        for key in NATIVE_NUMBERS:
            result.pop(key, None)
    return result


class PictureSettings(DataUpdateCoordinator):
    def __init__(self, hass, entry, display, controller, web=None):
        super().__init__(hass, _LOGGER, name="LG picture settings", update_interval=timedelta(seconds=60), config_entry=entry, always_update=False)
        self.entry, self.display, self.controller, self.web = entry, display, controller, web
        self._settings_lock = PriorityLock()
        self.awake = False
        self.last_action = None
        self._write_revision = 0

    def options_for(self, key):
        options = list(PICTURE_OPTIONS[key].options if key in PICTURE_OPTIONS else NATIVE_OPTIONS[key][1])
        # UH5F's external HDMI context rejects Auto. Retain it for readback
        # only when the device itself reports an automatic-only context.
        if key == "black_level" and is_uh5f(self.display.model_name):
            return ["auto"] if (self.data or {}).get(key) == "auto" else ["low", "high"]
        return options

    async def _power(self):
        if self.display.is_intentionally_unpowered:
            return False
        for attempt in range(3):
            power = await self.display.async_get_power_status(use_cache=False)
            if power is not None:
                return power
            if attempt < 2:
                await asyncio.sleep(.25)
        return None

    async def _read_one(self, key, *, background=False):
        spec = PICTURE_OPTIONS[key]
        polling = {"background_query": True} if background else {}
        if spec.parameter is None:
            value = await self.display.async_send_command(*spec.command, 0xFF, use_cache=False, **polling)
        elif spec.input_code is None:
            value = await self.display.async_get_subcommand(spec.command, spec.parameter, use_cache=False, **polling)
        else:
            response = await self.display.async_send_raw_command(*spec.command, spec.parameter, query_suffix=f" {spec.input_code:02x} ff", use_cache=False, **polling)
            payload = (ok_payload(response) or "").lower()
            prefix = f"{spec.parameter:02x}{spec.input_code:02x}"
            value = int(payload[-2:], 16) if len(payload) == 6 and payload.startswith(prefix) and re.fullmatch("[0-9a-f]{2}", payload[-2:]) else None
        return next((name for name, code in spec.options.items() if code == value), None)

    async def _native(self):
        if not self.web or not is_uh5f(await self.display.async_get_model_name()):
            return {}
        return await self.web.async_get_picture_options()

    async def _read_all(self):
        values = {}
        for key in PICTURE_OPTIONS:
            if (value := await self._read_one(key)) is not None:
                values[key] = value
        try:
            values.update(native_options(await self._native()))
        except LGWebError:
            pass  # A web outage must not disable independent RS232 options.
        return values

    async def _async_update_data(self):
        async with self._settings_lock:
            power = await self.display.async_get_power_status()
            if self.display.is_intentionally_unpowered or power is False:
                self.awake = False
                return {}
            if power is not True:
                self.awake = False
                raise UpdateFailed("Cannot read display power state")
            self.awake = True
            revision = (self.display.picture_context_revision, self._write_revision)
        # Release between queries so a mode change does not queue behind every
        # optional command timeout. Never publish a scan from an older context.
        values = {}
        for key in PICTURE_OPTIONS:
            async with self._settings_lock:
                if not self._scan_current(revision):
                    return dict(self.data or {}) if self.awake else {}
                if (value := await self._read_one(key, background=True)) is not None:
                    values[key] = value
        async with self._settings_lock:
            if not self._scan_current(revision):
                return dict(self.data or {}) if self.awake else {}
            try:
                values.update(native_options(await self._native()))
            except LGWebError:
                pass
            # Native I/O yields to independent power/source/energy controls.
            # Their final state must also invalidate the last response.
            if not self._scan_current(revision):
                return dict(self.data or {}) if self.awake else {}
        return values

    def _scan_current(self, revision):
        if self.display.is_intentionally_unpowered or self.display._last_power_status is False:
            self.awake = False
            return False
        return revision == (self.display.picture_context_revision, self._write_revision)

    async def _write_one(self, key, value):
        spec = PICTURE_OPTIONS[key]
        code = spec.options[value]
        if spec.parameter is None:
            await self.display.async_send_command(*spec.command, code)
        else:
            suffix = f" {code:02x}" if spec.input_code is None else f" {spec.input_code:02x} {code:02x}"
            await self.display.async_send_raw_command(*spec.command, spec.parameter, query_suffix=suffix, use_cache=False)

    @interactive_command
    async def async_set(self, key, value):
        options = (self.options_for(key) if key in PICTURE_OPTIONS or key in NATIVE_OPTIONS else
                   tuple(str(n) for n in range(-5, 6)) if key in NATIVE_NUMBERS else ())
        if value not in options:
            raise HomeAssistantError("Unsupported LG picture option")
        async with self._settings_lock, self.controller._control_lock:
            self._write_revision += 1
            if await self._power() is not True:
                self.awake = False
                raise HomeAssistantError("Display must be on to change picture settings")
            self.awake = True
            try:
                if key in NATIVE_OPTIONS or key in NATIVE_NUMBERS:
                    before_raw = await self._native()
                    before = native_options(before_raw).get(key)
                else:
                    before = await self._read_one(key)
                if before is None:
                    raise LGWebError("Picture option is unavailable in the current input/mode")
                if key in {"min_backlight", "max_backlight"}:
                    other = "max_backlight" if key == "min_backlight" else "min_backlight"
                    bound = await self._read_one(other)
                    if bound is None or (int(value) > int(bound) if key == "min_backlight" else int(value) < int(bound)):
                        raise LGWebError("Minimum backlight must not exceed maximum backlight")
                actual = before
                if before != value:
                    try:
                        if key in NATIVE_OPTIONS or key in NATIVE_NUMBERS:
                            await self.web.async_write_picture_option(key, value, before_raw["pictureMode"])
                        else:
                            await self._write_one(key, value)
                    except LGWebError:
                        pass
                    for attempt in range(3):
                        actual = native_options(await self._native()).get(key) if key in NATIVE_OPTIONS or key in NATIVE_NUMBERS else await self._read_one(key)
                        if actual == value:
                            break
                        if attempt < 2:
                            await asyncio.sleep(.25)
                values = dict(self.data or {})
                if actual is None:
                    values.pop(key, None)
                else:
                    values[key] = actual
                self.async_set_updated_data(values)
                if key in {"deep_color_hdmi1", "deep_color_hdmi2", "deep_color_hdmi3", "hdmi_it_content", "brightness_schedule", "hdr_picture_mode"}:
                    self.display._picture_settings_changed()
                if actual != value:
                    raise LGWebError("Display did not confirm the requested picture option")
            except LGWebError as err:
                raise HomeAssistantError(str(err)) from None

    @interactive_command
    async def async_action(self, action):
        if action not in PICTURE_ACTIONS:
            raise HomeAssistantError("Unsupported picture action")
        async with self._settings_lock, self.controller._control_lock:
            self._write_revision += 1
            if await self._power() is not True:
                raise HomeAssistantError("Display must be on to change picture settings")
            mode = await self.display.async_get_picture_mode(use_cache=False)
            if mode not in PICTURE_MODES.values():
                raise HomeAssistantError("Current picture mode is unknown")
            # These are one-shot commands. There is no read query for the action;
            # never replace a missing ACK with an assumption or replay the write.
            confirmed = await self.display.async_picture_action(action)
            self.display._picture_settings_changed()
            self.awake = True
            self.async_set_updated_data(await self._read_all())
            if not confirmed:
                raise HomeAssistantError("Picture action was not acknowledged; it may have applied. Check display settings before trying again")
            self.last_action = action


class PictureSettingEntity(CoordinatorEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self.key = key
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, coordinator.entry.entry_id)}}
        self._attr_icon = "mdi:television-shimmer"

    @property
    def available(self):
        return bool(super().available and self.coordinator.awake and not self.coordinator.display.is_intentionally_unpowered and self.coordinator.display._last_power_status is not False and (self.key in PICTURE_ACTIONS or self.key in (self.coordinator.data or {})))
