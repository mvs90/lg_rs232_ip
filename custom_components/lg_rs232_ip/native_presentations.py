"""Optional native Signage presentations, sharing the normal presentation queue."""

from __future__ import annotations

import asyncio

import aiohttp
from yarl import URL
from homeassistant.components.media_player import MediaPlayerState
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .web_manager import LGWebError

NATIVE_APP = "com.webos.app.dsmp"
EXTERNAL_APPS = {f"com.webos.app.hdmi{i}" for i in range(1, 5)}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


async def settle_mutation(coro):
    """Let a bounded write finish on cancellation so cleanup knows its outcome."""
    task = asyncio.create_task(coro)
    try:
        return await asyncio.shield(task), False
    except asyncio.CancelledError:
        # Caller must still receive the result (e.g. an uploaded asset path).
        # Return cancellation alongside it and re-raise after recording that result.
        return await task, True


class NativePresentations:
    @property
    def _web_manager(self):
        return self.hass.data[DOMAIN][self._config_entry.entry_id].get("web_manager")

    def _require_web_manager(self):
        if self._web_manager is None:
            raise ServiceValidationError(
                "Enable native LG web access in integration options first"
            )
        if self._ha_stopping:
            raise HomeAssistantError("Integration is stopping")
        return self._web_manager

    async def async_prepare_boot_image(self, media_id, media_directory="local"):
        from .boot_image import async_prepare_boot_image

        return await async_prepare_boot_image(self, media_id, media_directory)

    async def async_show_toast(self, message, priority="normal"):
        web = self._require_web_manager()
        self._check_presentation_policy(priority)
        async with self._control_lock:
            if (
                await self._lg_display.async_get_power_status(use_cache=False)
                is not True
            ):
                raise HomeAssistantError("Native toasts require an awake display")
            try:
                await web.async_toast(message)
            except LGWebError as err:
                raise HomeAssistantError(str(err)) from None

    async def async_show_native_image(self, media_id, duration=10, priority="normal"):
        self._require_web_manager()
        await self._enqueue_presentation(
            dict(
                kind="native_image",
                media_id=media_id,
                duration=duration,
                priority=priority,
            )
        )

    async def _async_download_native_image(self, media_id):
        # Never give an image server the LG credentials or its session cookies.
        try:
            media_id, _ = await self._async_resolve_media(
                media_id, "image", self.entity_id
            )
            url = URL(media_id)
            if (
                url.scheme not in {"http", "https"}
                or not url.host
                or url.user is not None
            ):
                raise ValueError
            session = async_get_clientsession(self.hass)
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=20)
            ) as response:
                response.raise_for_status()
                if (
                    response.content_length
                    and response.content_length > MAX_IMAGE_BYTES
                ):
                    raise ValueError
                image = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    image.extend(chunk)
                    if len(image) > MAX_IMAGE_BYTES:
                        raise ValueError
                return bytes(image)
        except Exception:
            # HA signed URLs and upstream exception strings must not enter diagnostics.
            raise HomeAssistantError(
                "Cannot load image; use an accessible image up to 5 MiB"
            ) from None

    async def _async_present_native_image(self, request):
        web = self._require_web_manager()
        asset = None
        snapshot = None
        launch_attempted = False
        launch_confirmed = False
        woke = False
        initial_app = None
        self._presentation_error = None
        try:
            self._check_presentation_policy(request["priority"])
            image = await self._async_download_native_image(request["media_id"])
            async with self._control_lock:
                self._check_presentation_policy(request["priority"])
                power = await self._lg_display.async_get_power_status(use_cache=False)
                if power is None:
                    raise HomeAssistantError("Display power is unknown")
                if not power and not self._config_entry.options.get(
                    "notification_wake_display", False
                ):
                    raise HomeAssistantError(
                        "Display is off and notification wake is disabled"
                    )
                previous_input = (
                    await self._lg_display.async_get_input(use_cache=False)
                    if power
                    else None
                )
                if power and previous_input is None:
                    raise HomeAssistantError("Cannot preserve the current input")
                snapshot = (power, previous_input)
                self._presentation_active = True
                self._standby_guard.reset()
                await self._async_cancel_wake()
                self._cancel_power_supply_off_task()
                if not power:
                    woke = True
                    await self._async_ensure_display_on_after_power_restore(
                        "native image"
                    )
                    if (
                        await self._lg_display.async_get_power_status(use_cache=False)
                        is not True
                    ):
                        raise HomeAssistantError("Display did not become ready")
                if woke:
                    wake_input = await self._lg_display.async_get_input(use_cache=False)
                    if wake_input is None:
                        raise HomeAssistantError(
                            "Cannot preserve input after waking display"
                        )
                    snapshot = (False, wake_input)
                initial_app = await web.async_foreground_app()
                if initial_app not in EXTERNAL_APPS:
                    raise HomeAssistantError(
                        "Native images require an external input; cannot restore an existing LG app session"
                    )
                # Shield bounded upload/launch writes from half-completed cancellation.
                asset, cancelled = await settle_mutation(web.async_upload_image(image))
                if cancelled:
                    raise asyncio.CancelledError
                # A physical source change during upload must not be overwritten.
                if await web.async_foreground_app() != initial_app:
                    raise HomeAssistantError(
                        "Display app changed during upload; presentation cancelled"
                    )
                launch_attempted = True
                async with self._lg_display.async_suppress_osd_for_switch():
                    _, cancelled = await settle_mutation(web.async_play_image(asset))
                    launch_confirmed = True
                    if cancelled:
                        raise asyncio.CancelledError
                self.async_write_ha_state()
            await asyncio.sleep(request["duration"])
        finally:
            async with self._control_lock:
                can_delete = not launch_attempted
                try:
                    if snapshot and (launch_attempted or woke):
                        current_power = await self._lg_display.async_get_power_status(
                            use_cache=False
                        )
                        app = (
                            await web.async_foreground_app()
                            if current_power is True
                            else None
                        )
                        # An uncertain launch may complete after the HTTP request fails.
                        # Give it a bounded settling window before deciding ownership.
                        if (
                            launch_attempted
                            and not launch_confirmed
                            and app == initial_app
                        ):
                            for _ in range(10):
                                await asyncio.sleep(0.5)
                                app = await web.async_foreground_app()
                                if app != initial_app:
                                    break
                        owns_screen = launch_attempted and app == NATIVE_APP
                        can_delete = current_power is False or (
                            launch_confirmed and app is not None and app != NATIVE_APP
                        )
                        if owns_screen or (
                            woke and app == initial_app and initial_app in EXTERNAL_APPS
                        ):
                            if snapshot[0]:
                                if not await self._lg_display.async_set_input(
                                    snapshot[1]
                                ):
                                    raise HomeAssistantError(
                                        "Could not restore display input"
                                    )
                                # RS232 input alone is not proof: it remains HDMI even in DSMP.
                                for _ in range(5):
                                    restored_app = await web.async_foreground_app()
                                    if restored_app in EXTERNAL_APPS:
                                        break
                                    await asyncio.sleep(0.4)
                                else:
                                    raise HomeAssistantError(
                                        "LG external input was not confirmed after restoration"
                                    )
                                self._current_input_id = snapshot[1]
                                self._source = self._resolve_source_name(snapshot[1])
                            else:
                                # Leave DSMP before standby so a pending OSD unlock
                                # can succeed while the external input is active.
                                if not await self._lg_display.async_set_input(
                                    snapshot[1]
                                ):
                                    raise HomeAssistantError(
                                        "Could not leave native playback before standby"
                                    )
                                if not await self._lg_display.async_power_off():
                                    raise HomeAssistantError(
                                        "Could not restore display standby"
                                    )
                                if (
                                    await self._lg_display.async_get_power_status(
                                        use_cache=False
                                    )
                                    is not False
                                ):
                                    raise HomeAssistantError(
                                        "Display standby was not confirmed"
                                    )
                                self._state = MediaPlayerState.OFF
                                self._last_display_power = False
                                self._schedule_power_supply_off(
                                    "native presentation complete"
                                )
                            can_delete = True
                except Exception as err:
                    self._presentation_error = str(err)
                finally:
                    try:
                        if asset and can_delete:
                            await web.async_delete_image(asset)
                        elif asset:
                            raise HomeAssistantError(
                                "Temporary LG image retained because restoration could not be confirmed; remove ha_lg_ files in Content Manager after leaving playback"
                            )
                    except Exception as err:
                        self._presentation_error = str(err)
                    await self._lg_display.async_restore_pending_osd()
                    self._presentation_active = False
                    self._standby_guard.reset()
                    self.async_write_ha_state()
