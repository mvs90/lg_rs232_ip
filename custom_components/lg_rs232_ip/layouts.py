"""Per-display layout storage and narrowly selected, cached Home Assistant data."""

import asyncio
from copy import deepcopy
from datetime import timedelta
import logging
import math
from astral import Observer
from astral.sun import elevation, azimuth
import time

from homeassistant.core import callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .layout_backgrounds import LayoutBackgrounds
from .layout_media import LayoutMedia
from .layout_camera import LayoutCamera
from .layout_cards import card_metadata
from .layout_config import (
    active_scenes,
    layout_entities,
    make_layout,
    media_background_entities,
    validate_layout,
)
from .layout_library import (
    from_config,
    source_views,
    sync_legacy,
    upgrade_library,
    validate_library,
)

_LOGGER = logging.getLogger(__name__)


class LayoutConflict(ValueError):
    """Another editor saved this document first."""


class DisplayLayouts:
    def __init__(self, hass, entry):
        self.hass, self.entry = hass, entry
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.layouts")
        self.backgrounds = LayoutBackgrounds(hass, entry.entry_id)
        self.media = LayoutMedia(hass)
        self.cameras = LayoutCamera(hass)
        self.config = make_layout()
        self.library = from_config(self.config)
        self.revision = 0
        self.changed = lambda: None
        self._lock = asyncio.Lock()
        self._unsub = self._timer = self._debounce = self._sun_timer = None
        self._sun_cache = None
        self._fetch_task = None
        self._cache = {}
        self._closed = False

    async def async_start(self):
        saved = await self.store.async_load()
        if saved:
            try:
                self.config = validate_layout(saved["config"])
                self.config, self.library = validate_library(
                    upgrade_library(
                        saved.get("library", from_config(self.config)), self.config
                    ),
                    self.config,
                )
                self.revision = int(saved.get("revision", 0))
            except (ValueError, TypeError, KeyError):
                self.config = make_layout()
                self.library = from_config(self.config)
                _LOGGER.warning(
                    "Invalid stored display layout; custom layouts disabled"
                )
        self._subscribe()

    async def async_close(self):
        self._closed = True
        await self.media.async_close()
        await self.cameras.async_close()
        for name in ("_unsub", "_timer", "_debounce", "_sun_timer"):
            if unsub := getattr(self, name):
                unsub()
                setattr(self, name, None)
        if self._fetch_task:
            self._fetch_task.cancel()
            await asyncio.gather(self._fetch_task, return_exceptions=True)
            self._fetch_task = None

    @property
    def source_views(self):
        return source_views(self.library)

    def document(self):
        return {"config": deepcopy(self.config), "revision": self.revision}

    def editor_document(self):
        return {
            "config": {**deepcopy(self.config), **deepcopy(self.library)},
            "revision": self.revision,
        }

    def all_scenes(self):
        return list(self.config["scenes"].values()) + [
            view["scene"] for view in self.library["views"]
        ]

    async def async_save(self, config, expected_revision, library=None):
        config = validate_layout(config)
        async with self._lock:
            if expected_revision != self.revision:
                raise LayoutConflict(
                    "Layout changed in another editor. Reload before saving."
                )
            library = sync_legacy(self.library, config) if library is None else library
            config, library = validate_library(library, config)
            images = {
                scene["image_id"]
                for scene in [v["scene"] for v in library["views"]]
                if scene["image_id"]
            }
            if images and not images.issubset(set(await self.backgrounds.async_list())):
                raise ValueError(
                    "Upload the missing background image on this installation first"
                )
            revision = self.revision + 1
            await self.store.async_save(
                {"config": config, "library": library, "revision": revision}
            )
            self.config, self.library, self.revision = config, library, revision
            if self._fetch_task:
                self._fetch_task.cancel()
                await asyncio.gather(self._fetch_task, return_exceptions=True)
                self._fetch_task = None
            self._cache.clear()
            self._subscribe()
            self.changed()
        return self.document()

    def _subscribe(self):
        if self._sun_timer:
            self._sun_timer()
            self._sun_timer = None
        self._sun_cache = None
        if self._unsub:
            self._unsub()
            self._unsub = None
        if self._timer:
            self._timer()
            self._timer = None
        if self._debounce:
            self._debounce()
            self._debounce = None
        if self.config["enabled"] and not self._closed:
            entities = layout_entities(self.config)
            if self.config.get("sun_entity"):
                entities.add(self.config["sun_entity"])
            if entities:
                self._unsub = async_track_state_change_event(
                    self.hass, entities, self._state_changed
                )
            self._schedule_fetch(1)
            self._schedule_sun()

    def _schedule_sun(self):
        if self.config.get("sun_entity") == "sun.sun":
            self._sun_timer = async_call_later(self.hass, 30, self._sun_tick)

    @callback
    def _sun_tick(self, _):
        self._sun_timer = None
        if self._closed or not self.config["enabled"]:
            return
        self._sun_cache = None
        self.changed()
        self._schedule_sun()

    @callback
    def _state_changed(self, _):
        # Coalesce high-rate sensors; do not create one task per state update.
        if self._debounce is None:
            self._debounce = async_call_later(self.hass, 0.3, self._publish)

    @callback
    def _publish(self, _):
        self._debounce = None
        if not self._closed:
            self.changed()

    def _schedule_fetch(self, delay=600):
        self._timer = async_call_later(self.hass, delay, self._fetch_tick)

    async def _fetch_tick(self, _):
        self._timer = None
        if self._closed or not self.config["enabled"]:
            return
        if not self._fetch_task:
            self._fetch_task = asyncio.create_task(self.async_refresh_data())
            try:
                await self._fetch_task
            finally:
                self._fetch_task = None
        if not self._closed and self.config["enabled"] and self._timer is None:
            self._schedule_fetch()

    def forecast_requests(self):
        requests = {}
        for scene in active_scenes(self.config).values():
            for item in scene["elements"]:
                entity = item["entity_id"]
                if not entity:
                    continue
                if item["kind"] == "calendar":
                    requests[entity, "calendar"] = 6
                elif item["kind"] == "weather" and item["forecast_type"] != "current":
                    key = entity, item["forecast_type"]
                    requests[key] = max(requests.get(key, 0), item["forecast_count"])
        return requests

    def sun(self):
        state = self.hass.states.get(self.config.get("sun_entity", "sun.sun"))
        if not state or state.state in ("unknown", "unavailable"):
            return None
        attrs = state.attributes
        if state.entity_id == "sun.sun":
            # Compute live position on HA; location never travels to the panel.
            if self._sun_cache and time.monotonic() - self._sun_cache[0] < 30:
                return dict(self._sun_cache[1])
            now = dt_util.utcnow()
            observer = Observer(
                self.hass.config.latitude,
                self.hass.config.longitude,
                self.hass.config.elevation,
            )
            try:
                e = elevation(observer, now)
                a = azimuth(observer, now)
                if not all(math.isfinite(v) for v in (e, a)):
                    raise ValueError("Invalid sun position")
                data = {
                    "elevation": round(e, 2),
                    "azimuth": round(a, 2),
                    "rising": attrs.get("rising") is True,
                    "is_daytime": e > -0.833,
                }
                self._sun_cache = (time.monotonic(), data)
                return dict(data)
            except (ValueError, TypeError):
                pass

        def number(key):
            try:
                value = float(attrs.get(key))
                return round(value, 1) if math.isfinite(value) else None
            except (ValueError, TypeError):
                return None

        return {
            "elevation": number("elevation"),
            "azimuth": number("azimuth"),
            "rising": attrs.get("rising") is True,
            "is_daytime": state.state == "above_horizon",
        }

    def _forecast_daytime(self, value):
        try:
            date = dt_util.parse_datetime(str(value))
            if date is None:
                return None
            if date.tzinfo is None:
                date = date.replace(
                    tzinfo=dt_util.get_time_zone(self.hass.config.time_zone)
                )
            observer = Observer(
                self.hass.config.latitude,
                self.hass.config.longitude,
                self.hass.config.elevation,
            )
            return elevation(observer, date) > -0.833
        except (ValueError, TypeError):
            return None

    async def async_refresh_data(self):
        """Fetch only requested forecast types; astronomy and decoding stay on HA."""
        if not self.config["enabled"] or not self.entry.options.get(
            "display_app_enabled", False
        ):
            return
        revision = self.revision
        requests = self.forecast_requests()
        semaphore = asyncio.Semaphore(2)

        async def fetch(key, count):
            entity_id, kind = key
            async with semaphore:
                try:
                    async with asyncio.timeout(8):
                        if kind == "calendar":
                            start = dt_util.now()
                            result = await self.hass.services.async_call(
                                "calendar",
                                "get_events",
                                {
                                    "entity_id": entity_id,
                                    "start_date_time": start.isoformat(),
                                    "end_date_time": (
                                        start + timedelta(days=7)
                                    ).isoformat(),
                                },
                                blocking=True,
                                return_response=True,
                            )
                            items = [
                                {
                                    k: str(event.get(k, ""))[:200]
                                    for k in ("summary", "start", "end", "location")
                                }
                                for event in result.get(entity_id, {}).get(
                                    "events", []
                                )[:count]
                            ]
                        else:
                            result = await self.hass.services.async_call(
                                "weather",
                                "get_forecasts",
                                {"entity_id": entity_id, "type": kind},
                                blocking=True,
                                return_response=True,
                            )
                            items = []
                            for row in result.get(entity_id, {}).get("forecast", [])[
                                :count
                            ]:
                                item = {
                                    k: str(row.get(k, ""))[:60]
                                    for k in (
                                        "datetime",
                                        "condition",
                                        "temperature",
                                        "templow",
                                        "precipitation_probability",
                                        "precipitation",
                                        "wind_speed",
                                    )
                                }
                                if kind == "hourly":
                                    item["is_daytime"] = (
                                        row.get("is_daytime")
                                        if type(row.get("is_daytime")) is bool
                                        else self._forecast_daytime(row.get("datetime"))
                                    )
                                items.append(item)
                    if revision == self.revision and not self._closed:
                        self._cache[key] = {"items": items, "updated": time.time()}
                except Exception:
                    if revision == self.revision and not self._closed:
                        if key in self._cache:
                            self._cache[key]["stale"] = True
                        else:
                            self._cache[key] = {
                                "items": [],
                                "updated": time.time(),
                                "unavailable": True,
                            }

        await asyncio.gather(*(fetch(key, count) for key, count in requests.items()))
        if revision == self.revision and not self._closed:
            self.changed()

    def media_entities(self):
        return media_background_entities(self.config) | {
            item["entity_id"]
            for scene in active_scenes(self.config).values()
            for item in scene["elements"]
            if item["kind"] == "media"
            and item.get("show_cover", True)
            and item["entity_id"]
        }

    def values(self, config=None):
        selected = config or self.config
        cards = {
            item["entity_id"]
            for scene in active_scenes(selected).values()
            for item in scene["elements"]
            if item["kind"] in ("media", "status")
        }
        media_entities = self.media_entities()
        values = {}
        for entity_id in layout_entities(selected):
            state = self.hass.states.get(entity_id)
            if not state:
                values[entity_id] = {
                    "state": "unavailable",
                    "name": entity_id,
                    "unit": "",
                }
                continue
            attrs = state.attributes
            value = {
                "state": state.state[:200],
                "name": str(attrs.get("friendly_name", entity_id))[:100],
                "unit": str(attrs.get("unit_of_measurement", ""))[:30],
            }
            if entity_id in cards:
                value.update(card_metadata(state))
            if entity_id in media_entities:
                value["artwork"] = self.media.key(entity_id)
            if entity_id.startswith("weather."):
                for key in (
                    "temperature",
                    "temperature_unit",
                    "humidity",
                    "wind_speed",
                    "wind_speed_unit",
                ):
                    value[key] = str(attrs.get(key, ""))[:60]
            if entity_id.startswith("calendar."):
                value["events"] = (
                    [
                        {
                            "summary": str(attrs.get("message", ""))[:200],
                            "start": self._calendar_date(attrs.get("start_time", "")),
                            "end": self._calendar_date(attrs.get("end_time", "")),
                        }
                    ]
                    if attrs.get("message")
                    else []
                )
            for kind in ("calendar", "daily", "hourly"):
                cached = self._cache.get((entity_id, kind))
                if not cached or time.time() - cached["updated"] >= 3600:
                    continue
                if cached.get("stale"):
                    value["stale"] = True
                if cached.get("unavailable"):
                    value.setdefault("forecast_unavailable", []).append(kind)
                    continue
                if kind == "calendar":
                    value["events"] = cached["items"]
                else:
                    value.setdefault("forecasts", {})[kind] = cached["items"]
                    if kind == "daily":
                        value["forecast"] = cached["items"]
            values[entity_id] = value
        return values

    def _calendar_date(self, value):
        value = str(value)[:60]
        if len(value) == 10:
            return value  # All-day events are dates, not UTC instants.
        try:
            parsed = dt_util.parse_datetime(value)
        except ValueError:
            return value
        if parsed and parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=dt_util.get_time_zone(self.hass.config.time_zone)
            )
        return parsed.isoformat() if parsed else value

    def payload(self):
        if not self.config["enabled"]:
            return None
        document = self.document()
        document["config"]["scenes"] = active_scenes(document["config"])
        return {
            **document,
            "values": self.values(),
            "sun": self.sun(),
            "timezone": str(self.hass.config.time_zone),
            "now": dt_util.utcnow().isoformat(),
        }
