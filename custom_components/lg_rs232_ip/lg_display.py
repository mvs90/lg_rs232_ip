"""LG Display communication via RS232/IP."""

import asyncio
from contextlib import asynccontextmanager
import logging
import re
import time

from .device_profile import decode_model, decode_software, ok_payload
from typing import Optional

_LOGGER = logging.getLogger(__name__)

# Import protocol constants
try:
    from .const import DEFAULT_DEVICE_ID, COMMAND_TIMEOUT, READ_STATUS
except ImportError:
    # Fallback for direct imports
    DEFAULT_DEVICE_ID = 0x01
    COMMAND_TIMEOUT = 1.0
    READ_STATUS = 0xFF

# How long to keep the display available after the last successful response
AVAILABILITY_TIMEOUT = 20.0
RECONNECT_BACKOFF_SECONDS = 5.0
CONNECT_ERROR_LOG_INTERVAL_SECONDS = 60.0
POWER_STATUS_CACHE_SECONDS = 2.0


class LGDisplay:
    """Class to communicate with LG Display via RS232 over IP."""

    def __init__(
        self,
        host: str,
        port: int = 9761,
        device_id: int = DEFAULT_DEVICE_ID,
        timeout: float = 3.0,
        power_transition_mode: bool = True,
        power_transition_timeout: float = 20.0,
    ):
        """Initialize the LG Display connection.

        Args:
            host: IP address of the LG Display
            port: TCP port (default: 9761 for RS232 over IP)
            device_id: Device ID for display (default: 0x01)
            timeout: Connection timeout in seconds
            power_transition_mode: Keep display available during power transitions
            power_transition_timeout: Time in seconds to preserve availability after disconnect
        """
        self.host = host
        self.port = port
        self.device_id = device_id
        self.timeout = timeout
        self.power_transition_mode = power_transition_mode
        self.power_transition_timeout = power_transition_timeout
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
        self._last_successful_response: Optional[float] = None
        self._command_lock = asyncio.Lock()  # Lock to synchronize command sending
        self._next_connect_attempt_at: float = 0.0
        self._last_connect_error_log_at: float = 0.0
        self._last_connect_error_message: Optional[str] = None
        self._power_supply_expected_off = False
        self._last_power_status: Optional[bool] = None
        self._last_power_status_at: float = 0.0
        self.model_name: str | None = None
        self.software_version: str | None = None
        self._query_cache = {}
        self._unsupported_until = {}
        self.suppress_osd_during_switch = False
        self.osd_restore_error = False
        self._osd_transition_lock = asyncio.Lock()
        self._osd_user_revision = 0
        self._osd_pending_restore_revision = None

    def set_power_supply_state(self, is_on: bool) -> None:
        """Hint whether the external power supply is expected to be on or off."""
        self._query_cache.clear()
        self._power_supply_expected_off = not is_on
        if is_on:
            self._next_connect_attempt_at = 0.0
            self._last_connect_error_message = None
            self._last_power_status = None
            self._last_power_status_at = 0.0
            return

        if self._writer is not None:
            self._writer.close()
        self._connected = False
        self._reader = None
        self._writer = None
        self._last_power_status = False
        self._last_power_status_at = time.monotonic()
        self._next_connect_attempt_at = time.monotonic() + RECONNECT_BACKOFF_SECONDS

    def _mark_temporarily_unavailable(
        self,
        message: str,
        *,
        retry_after: float = RECONNECT_BACKOFF_SECONDS,
    ) -> None:
        """Back off reconnect attempts briefly and avoid repeated log spam."""
        self._connected = False
        self._next_connect_attempt_at = time.monotonic() + retry_after

        now = time.monotonic()
        should_log = (
            self._last_connect_error_message != message
            or (now - self._last_connect_error_log_at)
            >= CONNECT_ERROR_LOG_INTERVAL_SECONDS
        )
        if should_log:
            _LOGGER.warning(message)
            self._last_connect_error_log_at = now
            self._last_connect_error_message = message

    async def async_connect(self) -> bool:
        """Connect to the LG Display."""
        if self._connected and self._reader and self._writer:
            return True

        now = time.monotonic()
        if self._power_supply_expected_off:
            return False

        if now < self._next_connect_attempt_at:
            return False

        try:
            if self._writer is not None:
                await self.async_disconnect()
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.timeout,
            )
            # Send wake-up command
            self._writer.write(b"\r")
            await self._writer.drain()
            await asyncio.sleep(0.2)  # Wait longer for display to wake up

            self._connected = True
            self._power_supply_expected_off = False
            self._next_connect_attempt_at = 0.0
            self._last_connect_error_message = None
            _LOGGER.info("Connected to LG Display at %s:%d", self.host, self.port)
            return True
        except asyncio.TimeoutError:
            self._mark_temporarily_unavailable(
                f"Timeout connecting to LG Display at {self.host}:{self.port}"
            )
            return False
        except Exception as err:
            self._mark_temporarily_unavailable(f"Error connecting to LG Display: {err}")
            return False

    async def async_disconnect(self) -> None:
        """Disconnect from the LG Display."""
        self._query_cache.clear()
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception as err:
                _LOGGER.warning("Error closing connection: %s", err)
        self._reader = None
        self._writer = None
        self._connected = False
        _LOGGER.debug("Disconnected from LG Display")

    async def async_send_raw_command(
        self,
        cmd1: str,
        cmd2: str,
        value: int,
        *,
        check_power: bool = False,
        query_suffix: str = "",
        use_cache: bool = True,
    ) -> Optional[str]:
        """Send raw LG RS232 command and get response.

        Command format: "cmd1 cmd2 device_id value\\r"
        Response format: "cmd2 device_id OK|NG hexvalue\\r"

        Args:
            cmd1: First command character
            cmd2: Second command character
            value: Value to send (0-255) or 0xFF to read status

        Returns:
            Response string or None if error
        """
        if check_power and (cmd1, cmd2) != ("k", "a"):
            power_status = await self.async_get_power_status(use_cache=True)
            if power_status is not True:
                return None

        async with self._command_lock:
            key = (cmd1, cmd2, value, query_suffix)
            is_query = value == READ_STATUS or query_suffix.strip().lower() == "ff"
            if is_query:
                if time.monotonic() < self._unsupported_until.get(key, 0):
                    return None
                cached = self._query_cache.get(key)
                if use_cache and cached and time.monotonic() - cached[0] < 2:
                    return cached[1]
            else:
                self._query_cache.clear()
            if not self._connected or not self._writer or not self._reader:
                if not await self.async_connect():
                    return None

            try:
                # Format: "cmd1 cmd2 device_id value\r"
                # Example: "ka 01 01\r" for power on, "kf 01 ff\r" to read volume
                if value == READ_STATUS:
                    # Use 0xFF to read current value for commands that support it
                    cmd_str = f"{cmd1}{cmd2} {self.device_id:02x} ff\r"
                else:
                    cmd_str = f"{cmd1}{cmd2} {self.device_id:02x} {value:02x}\r"

                _LOGGER.debug("Sending command: %s", cmd_str.strip())
                cmd_str = cmd_str.rstrip("\r") + query_suffix + "\r"
                cmd_bytes = cmd_str.encode("utf-8")
                _LOGGER.debug("Command bytes: %s", cmd_bytes)
                self._writer.write(cmd_bytes)
                await self._writer.drain()

                # TCP may split an ACK across packets. Only accept the requested
                # command and device, and never reuse a stream after a timeout.
                async with asyncio.timeout(COMMAND_TIMEOUT):
                    while True:
                        response = await self._reader.readuntil(b"x")
                        # x can also be the command letter (dx/fx/kx). The
                        # first delimiter is then the header, not the terminator.
                        if response.strip().lower() == b"x":
                            response += await self._reader.readuntil(b"x")
                        response_str = response.decode(
                            "ascii", errors="replace"
                        ).strip()
                        match = re.fullmatch(
                            rf"{cmd2}\s+{self.device_id:02x}\s+(?:OK|NG)[^\r\n]*x",
                            response_str,
                            re.IGNORECASE,
                        )
                        if match:
                            self._last_successful_response = time.monotonic()
                            if is_query:
                                if re.search(r"\sNG", response_str, re.IGNORECASE) and (
                                    cmd1,
                                    cmd2,
                                ) != ("k", "a"):
                                    self._unsupported_until[key] = (
                                        time.monotonic() + 300
                                    )
                                else:
                                    self._query_cache[key] = (
                                        time.monotonic(),
                                        response_str,
                                    )
                            return response_str
            except asyncio.CancelledError:
                self._query_cache.clear()
                await self.async_disconnect()
                raise
            except asyncio.TimeoutError:
                # Discard delayed replies so they cannot satisfy a later query.
                await self.async_disconnect()
                _LOGGER.debug("No response for command %s%s", cmd1, cmd2)
                return None
            except Exception as err:
                error_message = str(err)
                if (
                    "connection" in error_message.lower()
                    or "broken" in error_message.lower()
                ):
                    self._mark_temporarily_unavailable(
                        f"Error sending command: {error_message}",
                        retry_after=max(COMMAND_TIMEOUT, 5.0),
                    )
                    await self.async_disconnect()
                else:
                    _LOGGER.error("Error sending command: %s", err)
                    await self.async_disconnect()
                return None

    def _parse_response(self, response: str) -> Optional[int]:
        """Parse LG RS232 response.

        Response format: "cmd2 device_id OK|NG hexvalue"
        Example: "a 01 OK01" or "a 01 NG00"

        Args:
            response: Raw response string

        Returns:
            Parsed hex value or None if error
        """
        if not response:
            return None

        # Parse response pattern: cmd2 id OK|NG value
        # Example: "a 01 OK01" -> OK, value=01
        match = re.search(
            r"([a-z])\s+([0-9a-f]{2})\s+(OK|NG)([0-9a-f]+)?", response, re.IGNORECASE
        )
        if match:
            status = match.group(3).upper()
            value_str = match.group(4)

            if status == "OK" and value_str:
                try:
                    return int(value_str, 16)
                except ValueError:
                    pass
            elif status == "NG":
                _LOGGER.debug("Command returned NG status")
                return None

        _LOGGER.warning("Could not parse response: %s", response)
        return None

    async def async_send_command(
        self,
        cmd1: str,
        cmd2: str,
        value: int,
        *,
        check_power: bool = False,
        use_cache: bool = True,
    ) -> Optional[int]:
        """Send a command to the LG Display.

        Args:
            cmd1: First command character
            cmd2: Second command character
            value: Value to send (0-255) or READ_STATUS (0xFF) to query

        Returns:
            Parsed response value or None if error
        """
        response = await self.async_send_raw_command(
            cmd1,
            cmd2,
            value,
            check_power=check_power,
            use_cache=use_cache,
        )
        if response is None:
            return None
        return self._parse_response(response)

    async def async_power_on(self) -> bool:
        """Turn on the display."""
        result = await self.async_send_command("k", "a", 0x01, check_power=False)
        if result == 0x01:
            self._last_power_status = True
            self._last_power_status_at = time.monotonic()
            self._power_supply_expected_off = False
            return True
        return False

    async def async_power_off(self) -> bool:
        """Turn off the display."""
        result = await self.async_send_command("k", "a", 0x00, check_power=False)
        if result == 0x00:
            self._last_power_status = False
            self._last_power_status_at = time.monotonic()
            return True
        return False

    async def async_set_volume(self, volume: int) -> bool:
        """Set volume (0-100).

        Args:
            volume: Volume level 0-100

        Returns:
            True if successful
        """
        volume = max(0, min(100, volume))
        result = await self.async_send_command("k", "f", volume)
        return result is not None

    async def async_set_input(self, input_id: int) -> bool:
        """Set input source.

        Args:
            input_id: Input ID as hex value (e.g., 0x21 for HDMI1)

        Returns:
            True if successful
        """
        if isinstance(input_id, str):
            input_id = int(input_id, 16) if input_id.startswith("0x") else int(input_id)
        async with self.async_suppress_osd_for_switch():
            result = await self.async_send_command("x", "b", input_id)
            return result == input_id

    async def async_send_remote_key(self, key_code: int) -> bool:
        """Send a remote-control key code via mc command."""
        result = await self.async_send_command("m", "c", key_code)
        return result is not None

    async def async_volume_up_step(self) -> bool:
        """Send volume up key."""
        return await self.async_send_remote_key(0x02)

    async def async_volume_down_step(self) -> bool:
        """Send volume down key."""
        return await self.async_send_remote_key(0x03)

    async def async_key_right(self) -> bool:
        """Send right key."""
        return await self.async_send_remote_key(0x06)

    async def async_key_left(self) -> bool:
        """Send left key."""
        return await self.async_send_remote_key(0x07)

    async def async_get_power_status(self, *, use_cache: bool = True) -> Optional[bool]:
        """Get current power status.

        Returns:
            True if on, False if off, None if error
        """
        if self._power_supply_expected_off:
            self._last_power_status = False
            self._last_power_status_at = time.monotonic()
            return False

        now = time.monotonic()
        if (
            use_cache
            and self._last_power_status is not None
            and (now - self._last_power_status_at) < POWER_STATUS_CACHE_SECONDS
        ):
            return self._last_power_status

        result = await self.async_send_command(
            "k", "a", READ_STATUS, check_power=False, use_cache=use_cache
        )
        if result not in (0x00, 0x01):
            return None

        power_status = result == 0x01
        self._last_power_status = power_status
        self._last_power_status_at = now
        return power_status

    async def async_get_signal_status(self) -> Optional[bool]:
        """Read LG status check sv <id> 02 ff; unknown is never no-signal."""
        response = await self.async_send_raw_command(
            "s", "v", 0x02, query_suffix=" ff", use_cache=False
        )
        if response is None:
            return None
        value = self._parse_response(response)
        if value not in (0x0200, 0x0201):
            return None
        return value == 0x0201

    async def async_get_volume(self) -> Optional[int]:
        """Get current volume level.

        Returns:
            Volume level 0-100 or None if error
        """
        result = await self.async_send_command("k", "f", READ_STATUS)
        return result

    async def async_get_input(self, *, use_cache: bool = True) -> Optional[int]:
        """Get current input source.

        Returns:
            Input ID (hex value) or None if error
        """
        result = await self.async_send_command(
            "x", "b", READ_STATUS, use_cache=use_cache
        )
        return result

    async def async_get_model_name(self) -> str | None:
        if self.model_name is None:
            self.model_name = decode_model(
                await self.async_send_raw_command("f", "v", READ_STATUS)
            )
        return self.model_name

    async def async_get_software_version(self) -> str | None:
        # Version can change after a firmware update without recreating the entry.
        version = decode_software(
            await self.async_send_raw_command("f", "z", READ_STATUS)
        )
        if version is not None:
            self.software_version = version
        return version

    async def async_get_subcommand(self, command: str, parameter: int) -> int | None:
        """Read an sv/sn subcommand and validate its echoed parameter."""
        response = await self.async_send_raw_command(
            command[0], command[1], parameter, query_suffix=" ff"
        )
        payload = ok_payload(response)
        if not payload or not re.fullmatch(r"[0-9a-fA-F]{4,}", payload):
            return None
        if int(payload[:2], 16) != parameter:
            return None
        return int(payload[2:], 16)

    async def async_get_picture_mode(self) -> Optional[int]:
        """Get current picture mode."""
        result = await self.async_send_command("d", "x", READ_STATUS)
        return result

    async def async_set_picture_mode(self, mode: int) -> bool:
        """Set a picture mode."""
        result = await self.async_send_command("d", "x", mode)
        return result is not None

    async def async_get_auto_sleep(self) -> Optional[bool]:
        """Get auto sleep state."""
        result = await self.async_send_command("f", "g", READ_STATUS)
        if result is None:
            return None
        return result == 0x01

    async def async_set_auto_sleep(self, enabled: bool) -> bool:
        """Enable or disable auto sleep."""
        result = await self.async_send_command("f", "g", 0x01 if enabled else 0x00)
        return result is not None

    async def async_get_dpm(self) -> Optional[bool]:
        """Get DPM power management state."""
        result = await self.async_send_command("f", "j", READ_STATUS)
        if result not in range(8):
            return None
        return result != 0x00

    async def async_set_dpm(self, enabled: bool) -> bool:
        """Enable or disable DPM."""
        value = 0x04 if enabled else 0x00
        result = await self.async_send_command("f", "j", value)
        return result == value

    async def async_get_energy_saving(self) -> Optional[int]:
        """Get current energy saving level."""
        return await self.async_send_command("j", "q", READ_STATUS)

    async def async_set_energy_saving(self, mode: int) -> bool:
        """Set energy saving level."""
        result = await self.async_send_command("j", "q", mode)
        return result is not None

    async def async_get_osd_language(self) -> Optional[int]:
        """Get current OSD language."""
        return await self.async_send_command("f", "i", READ_STATUS)

    async def async_set_osd_language(self, language: int) -> bool:
        """Set the OSD language."""
        result = await self.async_send_command("f", "i", language)
        return result is not None

    async def async_get_sound_mode(self) -> Optional[int]:
        """Get current sound mode."""
        return await self.async_send_command("d", "y", READ_STATUS)

    async def async_set_sound_mode(self, mode: int) -> bool:
        """Set the sound mode."""
        result = await self.async_send_command("d", "y", mode)
        return result is not None

    async def async_get_backlight(self) -> Optional[int]:
        """Get current backlight level."""
        return await self.async_send_command("m", "g", READ_STATUS)

    async def async_set_backlight(self, level: int) -> bool:
        """Set backlight level."""
        result = await self.async_send_command("m", "g", level)
        return result is not None

    async def async_get_contrast(self) -> Optional[int]:
        """Get current contrast level."""
        return await self.async_send_command("k", "g", READ_STATUS)

    async def async_set_contrast(self, level: int) -> bool:
        """Set contrast level."""
        result = await self.async_send_command("k", "g", level)
        return result is not None

    async def async_get_color(self) -> Optional[int]:
        """Get current color level."""
        return await self.async_send_command("k", "i", READ_STATUS)

    async def async_set_color(self, level: int) -> bool:
        """Set color level."""
        result = await self.async_send_command("k", "i", level)
        return result is not None

    async def async_get_sharpness(self) -> Optional[int]:
        """Get current sharpness level."""
        return await self.async_send_command("k", "k", READ_STATUS)

    async def async_set_sharpness(self, level: int) -> bool:
        """Set sharpness level."""
        result = await self.async_send_command("k", "k", level)
        return result is not None

    async def async_get_tint(self) -> Optional[int]:
        """Get current tint level."""
        return await self.async_send_command("k", "j", READ_STATUS)

    async def async_set_tint(self, level: int) -> bool:
        """Set tint level."""
        result = await self.async_send_command("k", "j", level)
        return result is not None

    async def async_get_color_temperature(self) -> Optional[int]:
        """Get current color temperature value."""
        return await self.async_send_command("x", "u", READ_STATUS)

    async def async_set_color_temperature(self, value: int) -> bool:
        """Set color temperature value."""
        result = await self.async_send_command("x", "u", value)
        return result is not None

    async def async_get_remote_lock(self) -> Optional[bool]:
        """Get remote lock state."""
        result = await self.async_send_command("k", "m", READ_STATUS)
        if result is None:
            return None
        return result == 0x01

    async def async_set_remote_lock(self, enabled: bool) -> bool:
        """Enable or disable remote lock."""
        result = await self.async_send_command("k", "m", 0x01 if enabled else 0x00)
        return result is not None

    async def async_get_screen_mute(self) -> Optional[bool]:
        """Get screen mute state."""
        result = await self.async_send_command("k", "d", READ_STATUS)
        if result is None:
            return None
        return result == 0x01

    async def async_set_screen_mute(self, enabled: bool) -> bool:
        """Enable or disable screen mute."""
        result = await self.async_send_command("k", "d", 0x01 if enabled else 0x00)
        return result is not None

    async def async_get_osd_select(self, *, use_cache: bool = True) -> Optional[bool]:
        """Return OSD enabled/unlocked: kl 01; disabled/locked: kl 00."""
        result = await self.async_send_command(
            "k", "l", READ_STATUS, use_cache=use_cache
        )
        return bool(result) if result in (0, 1) else None

    async def _async_write_osd(self, enabled: bool) -> bool:
        return await self.async_send_command("k", "l", int(enabled)) == int(enabled)

    async def async_set_osd_select(self, enabled: bool) -> bool:
        """Explicit user intent supersedes any temporary OSD suppression."""
        self._osd_user_revision += 1
        self._osd_pending_restore_revision = None
        async with self._osd_transition_lock:
            result = await self._async_write_osd(enabled)
            if result:
                self.osd_restore_error = False
            return result

    async def _async_restore_owned_osd(self):
        """Restore a known temporary lock; native playback may reject unlock."""
        revision = self._osd_pending_restore_revision
        if revision is None or revision != self._osd_user_revision:
            return
        current = await self.async_get_osd_select(use_cache=False)
        if revision != self._osd_user_revision:
            return
        if current is False:
            restored = await self._async_write_osd(True)
        else:
            restored = current is True
        self.osd_restore_error = not restored
        if restored:
            self._osd_pending_restore_revision = None
        else:
            _LOGGER.debug("OSD restoration pending until display accepts unlock")

    async def async_restore_pending_osd(self):
        """Retry only our own pending restore, e.g. after leaving native playback."""
        async with self._osd_transition_lock:
            await self._async_restore_owned_osd()

    @asynccontextmanager
    async def async_suppress_osd_for_switch(self):
        """Temporarily lock OSD only if its fresh original state was enabled."""
        if not self.suppress_osd_during_switch:
            yield
            return
        async with self._osd_transition_lock:
            revision = self._osd_user_revision
            originally_enabled = await self.async_get_osd_select(use_cache=False)
            owned_lock = self._osd_pending_restore_revision == revision
            if originally_enabled is not True and not owned_lock:
                # Unknown is not permission to enable OSD later. Already-off stays off.
                yield
                return
            try:
                if originally_enabled is True:
                    self._osd_pending_restore_revision = revision
                    task = asyncio.create_task(self._async_write_osd(False))
                    try:
                        disabled = await asyncio.shield(task)
                    except asyncio.CancelledError:
                        await task
                        raise
                    if not disabled:
                        _LOGGER.warning(
                            "Display did not confirm temporary OSD suppression"
                        )
                yield
            finally:
                # Native DSMP may reject kl 01 until the return to HDMI. Retain
                # ownership across that return, never infer it from OSD=off alone.
                await asyncio.sleep(2)
                await self._async_restore_owned_osd()

    async def async_get_ism_method(self) -> Optional[int]:
        """Get ISM method value."""
        return await self.async_send_command("j", "p", READ_STATUS)

    async def async_set_ism_method(self, value: int) -> bool:
        """Set ISM method value."""
        result = await self.async_send_command("j", "p", value)
        return result is not None

    async def async_get_aspect_ratio(self) -> Optional[int]:
        """Get aspect ratio raw value."""
        return await self.async_send_command("k", "c", READ_STATUS)

    async def async_set_aspect_ratio(self, value: int) -> bool:
        """Set aspect ratio raw value."""
        result = await self.async_send_command("k", "c", value)
        return result is not None

    @property
    def is_connected(self) -> bool:
        """Check if currently connected to display."""
        return self._connected

    @property
    def is_intentionally_unpowered(self) -> bool:
        """Return True when the configured external power supply is intentionally off."""
        return self._power_supply_expected_off

    @property
    def has_successful_response(self) -> bool:
        """Return True once the display has responded at least once in this runtime."""
        return self._last_successful_response is not None

    @property
    def is_available(self) -> bool:
        """Return True if display should still be considered available."""
        if self._power_supply_expected_off:
            return False

        if self._connected:
            return True

        if not self.power_transition_mode:
            return False

        if self._last_successful_response is None:
            return False

        return (
            time.monotonic() - self._last_successful_response
        ) < self.power_transition_timeout
