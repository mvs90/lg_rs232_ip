"""Minute-precision local display clock, editable only with automatic time off."""

from homeassistant.components.datetime import DateTimeEntity
from .const import DOMAIN
from .maintenance import MaintenanceEntity


async def async_setup_entry(hass, entry, async_add_entities):
    if coordinator := hass.data[DOMAIN][entry.entry_id].get("maintenance"):
        async_add_entities([DisplayDateTime(coordinator)])


class DisplayDateTime(MaintenanceEntity, DateTimeEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator, "clock", "display_datetime", "mdi:calendar-clock")

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self.key)

    @property
    def extra_state_attributes(self):
        return {
            "display_timezone": (self.coordinator.data or {}).get("timezone"),
            "precision": "minute",
        }

    async def async_set_value(self, value):
        await self.coordinator.async_set(self.key, value)
