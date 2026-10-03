"""Per-display layout storage and narrowly selected, cached Home Assistant data."""

import asyncio
from copy import deepcopy
from datetime import timedelta
import logging
import time

from homeassistant.core import callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .layout_config import layout_entities, make_layout, validate_layout

_LOGGER = logging.getLogger(__name__)


class LayoutConflict(ValueError):
    """Another editor saved this document first."""


class DisplayLayouts:
    def __init__(self, hass, entry):
        self.hass, self.entry = hass, entry
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.layouts")
        self.config = make_layout()
        self.revision = 0
        self.changed = lambda: None
        self._lock = asyncio.Lock()
        self._unsub = self._timer = self._debounce = None
        self._fetch_task = None
        self._cache = {}
        self._closed = False

    async def async_start(self):
        saved = await self.store.async_load()
        if saved:
            try:
                self.config = validate_layout(saved["config"])
                self.revision = int(saved.get("revision", 0))
            except (ValueError, TypeError, KeyError):
                self.config = make_layout()
                _LOGGER.warning(
                    "Invalid stored display layout; custom layouts disabled"
                )
        self._subscribe()

    async def async_close(self):
        self._closed = True
        for name in ("_unsub", "_timer", "_debounce"):
            if unsub := getattr(self, name):
                unsub()
                setattr(self, name, None)
        if self._fetch_task:
            self._fetch_task.cancel()
            await asyncio.gather(self._fetch_task, return_exceptions=True)
            self._fetch_task = None

    def document(self):
        return {"config": deepcopy(self.config), "revision": self.revision}

    async def async_save(self, config, expected_revision):
        config = validate_layout(config)
        async with self._lock:
            if expected_revision != self.revision:
                raise LayoutConflict(
                    "Layout changed in another editor. Reload before saving."
                )
            revision = self.revision + 1
            await self.store.async_save({"config": config, "revision": revision})
            self.config, self.revision = config, revision
            if self._fetch_task:
                self._fetch_task.cancel()
                await asyncio.gather(self._fetch_task, return_exceptions=True)
                self._fetch_task = None
            self._cache.clear()
            self._subscribe()
            self.changed()
        return self.document()

    def _subscribe(self):
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
            if entities:
                self._unsub = async_track_state_change_event(
                    self.hass, entities, self._state_changed
                )
            self._schedule_fetch(1)

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

    async def async_refresh_data(self):
        """Calendar/forecast calls run on HA, never on the limited display CPU."""
        if not self.config["enabled"] or not self.entry.options.get(
            "display_app_enabled", False
        ):
            return
        revision = self.revision
        ids = layout_entities(self.config)
        semaphore = asyncio.Semaphore(2)

        async def fetch(entity_id):
            domain = entity_id.split(".")[0]
            if domain not in ("calendar", "weather"):
                return
            async with semaphore:
                try:
                    async with asyncio.timeout(8):
                        if domain == "calendar":
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
                            events = result.get(entity_id, {}).get("events", [])
                            value = {
                                "events": [
                                    {
                                        k: str(event.get(k, ""))[:200]
                                        for k in ("summary", "start", "end", "location")
                                    }
                                    for event in events[:6]
                                ]
                            }
                        else:
                            result = await self.hass.services.async_call(
                                "weather",
                                "get_forecasts",
                                {
                                    "entity_id": entity_id,
                                    "type": "daily",
                                },
                                blocking=True,
                                return_response=True,
                            )
                            items = result.get(entity_id, {}).get("forecast", [])
                            value = {
                                "forecast": [
                                    {
                                        k: str(item.get(k, ""))[:60]
                                        for k in (
                                            "datetime",
                                            "condition",
                                            "temperature",
                                            "templow",
                                        )
                                    }
                                    for item in items[:4]
                                ]
                            }
                    if revision == self.revision and not self._closed:
                        self._cache[entity_id] = {**value, "updated": time.time()}
                except Exception:
                    # Keep a bounded old forecast briefly; never include upstream
                    # errors, event descriptions or credentials in panel payloads.
                    if revision == self.revision and entity_id in self._cache:
                        self._cache[entity_id]["stale"] = True

        await asyncio.gather(*(fetch(entity_id) for entity_id in ids))
        if revision == self.revision and not self._closed:
            self.changed()

    def values(self, config=None):
        selected = config or self.config
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
            cached = self._cache.get(entity_id)
            if cached and time.time() - cached["updated"] < 3600:
                value.update({k: v for k, v in cached.items() if k != "updated"})
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
        return {
            **self.document(),
            "values": self.values(),
            "timezone": str(self.hass.config.time_zone),
            "now": dt_util.utcnow().isoformat(),
        }
