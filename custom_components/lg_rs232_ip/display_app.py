"""Optional, narrowly paired display app and reversible SI provisioning."""

from __future__ import annotations

import asyncio
import hmac
import hashlib
import ipaddress
import json
from pathlib import Path
import secrets
import time

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.network import get_url
from homeassistant.helpers.storage import Store
from homeassistant.helpers.event import async_track_state_change_event
from yarl import URL

from .const import DOMAIN
from .resident_app import ResidentApp, SI_APP_ID
from .platform_diagnostics import PlatformDiagnostics
from .web_manager import LGWebError

APP_VERSION = "1.20.0"
ASSETS = Path(__file__).parent / "www" / "display-app"


def validate_base_url(value):
    """The display needs a LAN-reachable address, never HA's localhost URL."""
    try:
        url = URL(value)
        if (
            url.scheme not in {"http", "https"}
            or not url.host
            or url.user is not None
            or url.query_string
            or url.fragment
            or url.path not in {"", "/"}
            or len(value) > 1024
            or any(ord(c) < 32 for c in value)
            or url.host.lower() in {"localhost", "localhost.localdomain"}
        ):
            raise ValueError
        try:
            address = ipaddress.ip_address(url.host)
        except ValueError:
            address = None
        if address and (
            address.is_loopback or address.is_unspecified or address.is_multicast
        ):
            raise ValueError
        return str(url).rstrip("/")
    except (ValueError, TypeError):
        raise ValueError(
            "Use the Home Assistant HTTP(S) address reachable from the display"
        ) from None


class DisplayAppManager(ResidentApp):
    """No HA login on the panel: its token permits only its own presentation."""

    def __init__(self, hass, entry, controller, web_manager):
        self.hass, self.entry = hass, entry
        self.controller, self.web = controller, web_manager
        self.enabled = entry.options.get("display_app_enabled", False)
        self.mode = entry.options.get("display_app_mode", "si")
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.display_app")
        self.saved = {}
        self.token = None
        self.assets = {}
        self.asset_digest = ""
        self.content = None
        self.last_seen = 0.0
        self.client_version = None
        self.client_layout_scene = None
        self.client_layout_revision = None
        self.client_has_bridge = False
        self.client_rendering = {}
        self.client_camera = {}
        self.client_offline = {}
        self.client_startup_design = {}
        self.platform = PlatformDiagnostics(self)
        self.last_error = None
        self._rendered = asyncio.Event()
        self.closed = False
        self.client_visible = False
        self.client_hdmi = False
        self.capture_capable = False
        self._capture_retry = 0.0
        self._capture = None
        self._capture_future = None
        self._revision = 0
        self._changed = asyncio.Event()
        self._sensor_unsub = None
        self._aspect_unsub = None
        self._init_resident()
        self.layouts = hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get("layouts")
        if self.layouts:
            self.layouts.changed = self._layouts_changed

    def _layouts_changed(self):
        if (
            self.saved.get("custom_view")
            and self.saved["custom_view"] not in self.view_sources
        ):
            self.saved["custom_view"] = None
            self.saved["dashboard"] = True
            self.saved["pip"] = self.saved["media_view"] = False
            self.store.async_delay_save(lambda: dict(self.saved), 1)
        self.changed()
        self._notify()

    async def async_start(self):
        self.saved = await self.store.async_load() or {}
        self.token = self.saved.get("token")
        if not self.token:
            self.token = secrets.token_urlsafe(32)
            self.saved["token"] = self.token
            await self.store.async_save(self.saved)
        if self.enabled:
            self._aspect_unsub = self.controller._lg_display.subscribe_aspect_ratio(
                self.changed
            )
            self.assets = await self.hass.async_add_executor_job(
                lambda: {
                    name: (ASSETS / name).read_bytes()
                    for name in (
                        "index.html",
                        "app.js",
                        "app.css",
                        "layout.js",
                        "weather.js",
                        "cards.js",
                        "layout.css",
                        "grain.png",
                        "camera.js",
                        "offline.js",
                        "startup.js",
                        "startup-design.js",
                        "platform.js",
                        "wall.js",
                        "test-stream.m3u8",
                        "test-stream.ts",
                    )
                }
            )
            self.asset_digest = hashlib.sha256(
                b"".join(self.assets[name] for name in sorted(self.assets))
            ).hexdigest()[:16]
            entities = self.entry.options.get("display_app_entities", [])[:12]
            if entities:

                @callback
                def sensor_changed(_):
                    if self.content and self.content["dashboard"]:
                        self.changed()

                self._sensor_unsub = async_track_state_change_event(
                    self.hass, entities, sensor_changed
                )

    async def async_close(self):
        self.closed = True
        self.platform.close()
        if self._aspect_unsub:
            self._aspect_unsub()
            self._aspect_unsub = None
        if self._sensor_unsub:
            self._sensor_unsub()
            self._sensor_unsub = None
        self.content = None
        self._rendered.set()
        self.changed()
        if self._capture_future and not self._capture_future.done():
            self._capture_future.set_result(None)

    @property
    def connected(self):
        return bool(
            self.enabled
            and not self.closed
            and self.client_visible
            and self.client_version == APP_VERSION
            and self.last_seen
            and time.monotonic() - self.last_seen < 12
        )

    def changed(self):
        self._revision += 1
        self._changed.set()

    async def async_state(self, revision):
        if str(self._revision) == revision and not self.closed:
            self._changed.clear()
            try:
                await asyncio.wait_for(self._changed.wait(), 25)
            except TimeoutError:
                pass
        return self.state()

    async def async_capture(self, height):
        if (
            not self.connected
            or not self.capture_capable
            or time.monotonic() < self._capture_retry
            or self._capture is not None
        ):
            return None
        identifier = secrets.token_hex(16)
        future = self._capture_future = asyncio.get_running_loop().create_future()
        self._capture = {"id": identifier, "height": height}
        self.changed()
        try:
            result = await asyncio.wait_for(asyncio.shield(future), 3)
            if result is None:
                self._capture_retry = time.monotonic() + 30
            return result
        except TimeoutError:
            self._capture_retry = time.monotonic() + 30
            return None
        finally:
            if not future.done():
                future.cancel()
            self._capture = self._capture_future = None
            self.changed()

    def accept_frame(self, identifier, image):
        if (
            not self.connected
            or not self._capture
            or self._capture["id"] != identifier
            or not self._capture_future
            or self._capture_future.done()
        ):
            raise ValueError
        if not image.startswith(b"\xff\xd8\xff") or not image.endswith(b"\xff\xd9"):
            raise ValueError
        self._capture_future.set_result(image)

    @property
    def status(self):
        if not self.enabled:
            return "disabled"
        if self.last_error:
            return "error"
        if self.connected:
            return "connected"
        return "configured" if self.saved.get("installed") else "ready"

    @property
    def attributes(self):
        return {
            "launch_mode": self.mode,
            "resident_enabled": self.resident,
            "dashboard_selected": self.dashboard_selected,
            "pip_selected": self.pip_selected,
            "media_view_selected": self.media_view_selected,
            "selected_view": self.selected_view,
            "resident_connected": self.resident_connected,
            "resident_paused": bool(self.saved.get("paused")),
            "capture_capable": self.connected and self.capture_capable,
            "hdmi_signal_ready": self.client_hdmi if self.connected else False,
            "app_version": APP_VERSION,
            "client_version": self.client_version,
            "layout_scene": self.client_layout_scene if self.connected else None,
            "layout_revision": self.client_layout_revision if self.connected else None,
            "platform_bridge_present": self.client_has_bridge,
            "rendering": self.client_rendering if self.connected else {},
            "camera_widget": self.client_camera if self.connected else {},
            "offline_start": self.client_offline if self.connected else {},
            "startup_design": self.client_startup_design if self.connected else {},
            "platform_diagnostics": self.platform.data,
            "si_configured": bool(self.saved.get("installed")),
            "si_restore_pending": "previous" in self.saved and not self.resident,
            "last_error": self.last_error,
        }

    def url(self):
        if not self.enabled or self.closed:
            raise HomeAssistantError(
                "Enable the display app in LG integration options first"
            )
        try:
            base = validate_base_url(
                self.entry.options.get("display_app_base_url")
                or get_url(self.hass, prefer_external=False)
            )
        except Exception:
            raise HomeAssistantError(
                "Set an LG-accessible Home Assistant URL in the display app options"
            ) from None
        return f"{base}/api/{DOMAIN}/display_app/{self.entry.entry_id}/{self.token}/index.html"

    def _notify(self):
        self.controller.async_write_ha_state()

    def _require_idle_awake(self):
        if self.controller.presentation_active or self.controller.external_owner:
            raise HomeAssistantError(
                "Stop the current presentation before changing SI settings"
            )

    async def async_prepare_si(self, original_app, original_power, *, resident=False):
        """Called under the controller lock. SI changes last for one presentation."""
        if "previous" in self.saved:
            await self.async_recover_si()
        previous = await self.web.async_get_si_settings()
        if previous["appLaunchMode"] != "none":
            raise HomeAssistantError(
                "An existing SI application is configured; it will not be replaced"
            )
        address = self.url()
        desired = {
            **previous,
            "appLaunchMode": "remote",
            "appType": "zip",
            "fqdnMode": "on",
            "fqdnAddr": address,
            "secureConnection": "on" if address.startswith("https:") else "off",
        }
        original_input = None
        if resident:
            original_input = await self.controller._lg_display.async_get_input(
                use_cache=False
            )
            if original_input is None:
                raise HomeAssistantError("Cannot preserve input for resident app")
        self.saved.update(
            previous=previous,
            attempted=desired,
            original_app=original_app,
            original_power=original_power,
        )
        if resident:
            self.saved["resident"] = True
            self.saved["original_input"] = original_input
        await self.store.async_save(self.saved)
        try:
            await self.web.async_set_si_settings(desired)
            self.saved["installed"] = desired
            await self.store.async_save(self.saved)
            self.last_error = None
        except LGWebError:
            self.last_error = "si_setup_unconfirmed"
            raise HomeAssistantError(
                "SI setup was not confirmed; original settings are saved for restoration"
            ) from None
        finally:
            self._notify()

    async def async_owns_si(self):
        current = await self.web.async_get_si_settings()
        return current == self.saved.get("installed") or current == self.saved.get(
            "attempted"
        )

    async def async_recover_si(self):
        """Called under the controller lock, including after an interrupted HA run."""
        previous = self.saved.get("previous")
        if previous is None:
            return
        if (
            await self.controller._lg_display.async_get_power_status(use_cache=False)
            is not True
        ):
            raise HomeAssistantError(
                "SI restoration pending until the display is awake"
            )
        current = await self.web.async_get_si_settings()
        if current != previous:
            if current not in [
                self.saved.get("installed"),
                self.saved.get("attempted"),
            ]:
                self.last_error = "si_settings_changed_externally"
                raise HomeAssistantError(
                    "SI settings changed outside Home Assistant; restoration stopped"
                )
            if await self.web.async_foreground_app() == SI_APP_ID:
                original = self.selected_app
                if original not in {f"com.webos.app.hdmi{i}" for i in range(1, 5)}:
                    raise HomeAssistantError("Original HDMI input is unknown")
                async with self.controller._lg_display.async_suppress_osd_for_switch():
                    await self.web.async_launch_app(original)
            await self.web.async_set_si_settings(previous)
        for key in (
            "previous",
            "installed",
            "attempted",
            "original_app",
            "original_power",
            "original_input",
            "selected_input",
            "selected_app",
            "resident",
            "auto_retry",
        ):
            self.saved.pop(key, None)
        await self.store.async_save(self.saved)
        if self.last_error and self.last_error.startswith("si_"):
            self.last_error = None
        self._notify()

    async def async_restore_si(self):
        from .native_presentations import settle_mutation

        async with self.controller._control_lock:
            self._require_idle_awake()
            if self.resident:
                self.saved["paused"] = True
            _, cancelled = await settle_mutation(self.async_recover_si())
            if cancelled:
                raise asyncio.CancelledError

    async def async_maybe_recover(self, *, power="query"):
        """Retry after a sleeping/disconnected display returns, without waking it."""
        if self.resident:
            await self.async_maintain_resident(power=power)
            return
        if (
            "previous" not in self.saved
            or self.controller._control_lock.locked()
            or self.controller.presentation_active
            or self.controller.external_owner
            or self.last_error == "si_settings_changed_externally"
        ):
            return
        try:
            await self.async_restore_si()
        except (HomeAssistantError, LGWebError):
            if self.last_error != "si_settings_changed_externally":
                self.last_error = "si_recovery_pending"
            self._notify()

    def begin(self, title, message, duration, dashboard=False, layout="fullscreen"):
        if self.content is not None:
            raise HomeAssistantError("A display app presentation is already active")
        if layout not in {"fullscreen", "overlay", "pip"} or (
            layout != "fullscreen" and self.mode != "si"
        ):
            raise HomeAssistantError(
                "HDMI overlay and picture-in-picture require SI mode"
            )
        self.url()  # Check configuration before allocating presentation state.
        self._rendered.clear()
        self.last_error = None
        self.content = {
            "id": secrets.token_hex(16),
            "title": title,
            "message": message,
            "duration": duration,
            "dashboard": dashboard,
            "layout": layout,
            "hdmi": None,
            "expires": time.monotonic() + duration + 360,
        }
        self.changed()
        return self.content["id"]

    def end(self, identifier):
        if self.content and self.content["id"] == identifier:
            self.content = None
            self._rendered.set()
            self.changed()

    async def wait_rendered(self, identifier):
        try:
            await asyncio.wait_for(self._rendered.wait(), 15)
        except TimeoutError:
            self.last_error = "render_timeout"
            self._notify()
            raise HomeAssistantError(
                "Display app did not confirm rendering; check its Home Assistant URL"
            ) from None
        if (
            self.closed
            or not self.content
            or self.content["id"] != identifier
            or self.last_error
        ):
            raise HomeAssistantError("Display app presentation failed or was cancelled")

    def state(self):
        base = {
            "version": APP_VERSION,
            "revision": self._revision,
            "idle_hdmi": self.idle_hdmi(),
            "hdmi_fit": "fill"
            if self.controller._lg_display.aspect_ratio == 2
            else "contain",
            "dashboard": self.dashboard_selected,
            "pip": self.pip_selected,
            "media_view": self.media_view_selected,
            "selected_view": self.selected_view,
            "startup": self.startup,
            "startup_design_version": self.layouts.startup_design.version if self.layouts else None,
            "capture": self._capture,
            "diagnostics": self.platform.ticket,
            "offline_enabled": self.resident and self.entry.options.get("display_app_offline", False),
            "input_request": self._input_request,
            "input_transition": self._input_transition,
            "layout": self.layouts.payload() if self.layouts else None,
        }
        content = self.content
        if not content or content["expires"] <= time.monotonic():
            return {**base, "content": None}
        payload = {
            key: content[key]
            for key in ("id", "title", "message", "duration", "layout", "hdmi")
        }
        payload["rendered"] = bool(content.get("rendered"))
        payload["remaining"] = max(0, int(content["expires"] - time.monotonic()))
        payload["cards"] = []
        if content["dashboard"]:
            for entity_id in self.entry.options.get("display_app_entities", [])[:12]:
                if entity_id.split(".")[0] not in {"sensor", "binary_sensor"}:
                    continue
                if state := self.hass.states.get(entity_id):
                    payload["cards"].append(
                        {
                            "name": str(
                                state.attributes.get("friendly_name", entity_id)
                            )[:100],
                            "value": state.state[:100],
                            "unit": str(
                                state.attributes.get("unit_of_measurement", "")
                            )[:30],
                        }
                    )
        return {**base, "content": payload}

    def event(self, value):
        if isinstance(value, dict) and value.get("type") == "diagnostics":
            self.platform.accept(value)
            return
        if not isinstance(value, dict) or value.get("type") not in {
            "hello",
            "heartbeat",
            "rendered",
            "error",
            "capture_error",
            "input_applied",
        }:
            raise ValueError
        before = (
            self.connected,
            self.client_version,
            dict(self.client_rendering),
            dict(self.client_camera),
            dict(self.client_offline),
            dict(self.client_startup_design),
            self.client_layout_scene,
            self.client_layout_revision,
            self.client_hdmi,
            self.capture_capable,
            self.last_error,
        )
        if value["type"] == "hello":
            version = value.get("version")
            if not isinstance(version, str) or len(version) > 24:
                raise ValueError
            self.client_version = version
            self.client_has_bridge = value.get("bridge") is True
        if value["type"] in {"hello", "heartbeat"}:
            scene = value.get("layout_scene")
            revision = value.get("layout_revision")
            self.client_layout_scene = (
                scene
                if isinstance(scene, str)
                and scene
                in (
                    self.layouts.config["scenes"]
                    if self.layouts
                    else (
                        "signal",
                        "no_signal",
                        "dashboard",
                        "pip_view",
                        "media_view",
                        "overlay",
                        "pip",
                        "fullscreen",
                    )
                )
                else None
            )
            self.client_layout_revision = (
                revision if type(revision) is int and revision >= 0 else None
            )
            rendering = value.get("rendering")
            if isinstance(rendering, dict):
                self.client_rendering = {
                    key: rendering[key]
                    for key in ("width", "height", "screen_width", "screen_height")
                    if type(rendering.get(key)) is int and 1 <= rendering[key] <= 8192
                }
                ratio = rendering.get("pixel_ratio")
                if type(ratio) in (int, float) and 0.5 <= ratio <= 4:
                    self.client_rendering["pixel_ratio"] = ratio
            offline = value.get("offline", {})
            if isinstance(offline, dict):
                self.client_offline = {
                    key: offline.get(key) is True
                    for key in ("enabled", "supported", "restored_hdmi")
                }
                status = offline.get("cache_status")
                if type(status) is int and 0 <= status <= 5:
                    self.client_offline["cache_status"] = status
            startup_design = value.get("startup_design", {})
            if isinstance(startup_design, dict):
                version = startup_design.get("version")
                self.client_startup_design = {
                    "version": version if isinstance(version, str) and len(version) == 64 and all(c in "0123456789abcdef" for c in version) else None,
                    "cached": startup_design.get("cached") is True,
                    "image_cached": startup_design.get("image_cached") is True,
                }
            camera_status = value.get("camera", {})
            if isinstance(camera_status, dict):
                self.client_camera = {
                    "mode": camera_status.get("mode")
                    if camera_status.get("mode") in ("inactive", "stream", "snapshot")
                    else "inactive",
                    "ready": camera_status.get("ready") is True,
                    **{
                        key: camera_status[key]
                        for key in ("width", "height")
                        if type(camera_status.get(key)) is int
                        and 0 <= camera_status[key] <= 8192
                    },
                }
            self.client_visible = value.get("visible") is True
            self.client_hdmi = value.get("hdmi_ready") is True
            self.capture_capable = value.get("capture") is True
        self.last_seen = time.monotonic()
        if (
            value["type"] == "input_applied"
            and self._input_request
            and value.get("id") == self._input_request
        ):
            self._input_applied.set()
        if (
            value["type"] == "capture_error"
            and self._capture
            and value.get("id") == self._capture["id"]
        ):
            if self._capture_future and not self._capture_future.done():
                self._capture_future.set_result(None)
        content = self.content
        if content and value.get("id") == content["id"]:
            if value["type"] == "error":
                self.last_error = "render_failed"
                self._rendered.set()
            elif value["type"] == "rendered":
                # The display's timer starts after actual rendering, not during launch.
                if not content.get("rendered"):
                    content["rendered"] = True
                    content["expires"] = time.monotonic() + content["duration"]
                self._rendered.set()
        after = (
            self.connected,
            self.client_version,
            dict(self.client_rendering),
            dict(self.client_camera),
            dict(self.client_offline),
            dict(self.client_startup_design),
            self.client_layout_scene,
            self.client_layout_revision,
            self.client_hdmi,
            self.capture_capable,
            self.last_error,
        )
        if before != after:
            self._notify()


class DisplayAppView(HomeAssistantView):
    url = "/api/lg_rs232_ip/display_app/{entry_id}/{token}/{resource}"
    name = "api:lg_rs232_ip:display_app"
    requires_auth = False

    def __init__(self, hass):
        self.hass = hass

    def _manager(self, request, entry_id, token):
        manager = self.hass.data.get(DOMAIN, {}).get(entry_id, {}).get("display_app")
        if (
            not manager
            or not manager.enabled
            or manager.closed
            or not manager.token
            or not hmac.compare_digest(token.encode(), manager.token.encode())
        ):
            raise web.HTTPNotFound()
        return manager

    async def get(self, request, entry_id, token, resource):
        manager = self._manager(request, entry_id, token)
        headers = {
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; media-src 'self' ext: udp:; manifest-src 'self'; frame-ancestors 'none'",
        }
        if resource == "offline.appcache":
            if not manager.resident or not manager.entry.options.get(
                "display_app_offline", False
            ):
                # A 404 obsoletes a previously opted-in browser cache.
                raise web.HTTPNotFound()
            names = [
                name
                for name in manager.assets
                if name not in ("test-stream.ts", "test-stream.m3u8")
            ]
            return web.Response(
                text="CACHE MANIFEST\n# "
                + APP_VERSION
                + " "
                + manager.asset_digest
                + "\nCACHE:\n"
                + "\n".join(names)
                + "\nNETWORK:\n*\n",
                content_type="text/cache-manifest",
                headers={**headers, "Cache-Control": "no-cache"},
            )
        if resource == "startup":
            return web.json_response({"startup": manager.startup, "design_version": manager.layouts.startup_design.version if manager.layouts else None}, headers=headers)
        if resource == "startup-design" and manager.layouts:
            try:
                bundle = await manager.layouts.startup_design.async_bundle()
            except (ValueError, OSError):
                raise web.HTTPServiceUnavailable() from None
            return web.json_response(bundle, headers=headers, dumps=lambda value: json.dumps(value, ensure_ascii=False))
        if resource == "state":
            return web.json_response(
                await manager.async_state(request.query.get("since")), headers=headers
            )
        if resource in ("camera.json", "camera.jpg") and manager.layouts:
            from .layout_config import active_scenes

            scene = active_scenes(manager.layouts.config).get(
                request.query.get("view"), {}
            )
            item = next(
                (
                    item
                    for item in scene.get("elements", [])
                    if item["id"] == request.query.get("id")
                    and item["kind"] == "camera"
                ),
                None,
            )
            if (
                not manager.layouts.config["enabled"]
                or not item
                or item["camera_source"] != "entity"
            ):
                raise web.HTTPNotFound()
            if resource == "camera.json":
                url = None
                if item["camera_mode"] != "snapshot":
                    url = await manager.layouts.cameras.async_get(
                        item["entity_id"], "stream"
                    )
                return web.json_response({"stream": url}, headers=headers)
            data = await manager.layouts.cameras.async_get(item["entity_id"], "image")
            return web.Response(
                body=data,
                status=200 if data else 204,
                content_type="image/jpeg",
                headers=headers,
            )
        if resource == "cover.jpg" and manager.layouts:
            entity = request.query.get("entity", "")
            if (
                not manager.layouts.config["enabled"]
                or entity not in manager.layouts.media_entities()
            ):
                raise web.HTTPNotFound()
            from .layout_media import artwork_size

            try:
                size = artwork_size(request.query.get("size", "640"))
            except ValueError as err:
                raise web.HTTPBadRequest(text=str(err)) from None
            data = await manager.layouts.media.async_image(
                entity, request.query.get("v"), size
            )
            return web.Response(
                body=data,
                status=200 if data else 204,
                content_type="image/jpeg",
                headers=headers,
            )
        if resource == "background.jpg" and manager.layouts:
            from .layout_config import active_scenes

            identifier = request.query.get("id", "")
            if not any(
                scene.get("image_id") == identifier and identifier
                for scene in active_scenes(manager.layouts.config).values()
            ):
                raise web.HTTPNotFound()
            try:
                data = await manager.layouts.backgrounds.async_read(identifier)
            except (ValueError, FileNotFoundError):
                raise web.HTTPNotFound() from None
            return web.Response(
                body=data,
                content_type="image/jpeg",
                headers={**headers, "Cache-Control": "private, max-age=86400"},
            )
        mime = {
            "index.html": "text/html",
            "app.js": "application/javascript",
            "app.css": "text/css",
            "layout.js": "application/javascript",
            "weather.js": "application/javascript",
            "cards.js": "application/javascript",
            "layout.css": "text/css",
            "grain.png": "image/png",
            "camera.js": "application/javascript",
            "offline.js": "application/javascript",
            "startup.js": "application/javascript",
            "startup-design.js": "application/javascript",
            "platform.js": "application/javascript",
            "wall.js": "application/javascript",
            "test-stream.m3u8": "application/vnd.apple.mpegurl",
            "test-stream.ts": "video/mp2t",
        }
        if resource not in mime:
            raise web.HTTPNotFound()
        body = manager.assets[resource]
        if (
            resource == "index.html"
            and manager.resident
            and manager.entry.options.get("display_app_offline", False)
        ):
            hdmi = manager.idle_hdmi() or ""
            body = body.replace(
                b'<html lang="de">',
                (
                    '<html lang="de" manifest="offline.appcache" data-offline-hdmi="'
                    + hdmi
                    + '">'
                ).encode(),
            )
        return web.Response(body=body, content_type=mime[resource], headers=headers)

    async def post(self, request, entry_id, token, resource):
        manager = self._manager(request, entry_id, token)
        if resource == "frame":
            identifier = request.query.get("id")
            if not manager._capture or manager._capture["id"] != identifier:
                raise web.HTTPConflict()
            raw = bytearray()
            async for chunk in request.content.iter_chunked(65536):
                raw.extend(chunk)
                if len(raw) > 5 * 1024 * 1024:
                    raise web.HTTPRequestEntityTooLarge(
                        max_size=5 * 1024 * 1024, actual_size=len(raw)
                    )
            try:
                manager.accept_frame(identifier, bytes(raw))
            except ValueError:
                raise web.HTTPBadRequest() from None
            return web.json_response(
                {"ok": True}, headers={"Cache-Control": "no-store"}
            )
        if resource != "event":
            raise web.HTTPNotFound()
        raw = bytearray()
        async for chunk in request.content.iter_chunked(4097):
            raw.extend(chunk)
            if len(raw) > 4096:
                raise web.HTTPRequestEntityTooLarge(max_size=4096, actual_size=len(raw))
        try:
            manager.event(json.loads(raw))
        except (ValueError, TypeError):
            raise web.HTTPBadRequest() from None
        return web.json_response({"ok": True}, headers={"Cache-Control": "no-store"})
