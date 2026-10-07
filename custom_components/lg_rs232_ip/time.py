"""ISM schedule times; unrelated modes do not offer ineffective controls."""

from datetime import time
from homeassistant.components.time import TimeEntity
from .const import DOMAIN
from .maintenance import MaintenanceEntity


async def async_setup_entry(hass, entry, async_add_entities):
    if coordinator := hass.data[DOMAIN][entry.entry_id].get("maintenance"):
        async_add_entities(
            [
                IsmTime(coordinator, "ismStartTime", "ism_start"),
                IsmTime(coordinator, "ismEndTime", "ism_end"),
            ]
        )


class IsmTime(MaintenanceEntity, TimeEntity):
    def __init__(self, coordinator, key, translation_key):
        super().__init__(coordinator, key, translation_key, "mdi:clock-outline")

    @property
    def native_value(self):
        value = (self.coordinator.data or {}).get(self.key)
        return time(*divmod(int(value), 60)) if value is not None else None

    async def async_set_value(self, value):
        await self.coordinator.async_set(self.key, value.hour * 60 + value.minute)
