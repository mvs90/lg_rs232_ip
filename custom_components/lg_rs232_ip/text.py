"""Physical LG Signage name, independent of the HA device name."""

from homeassistant.components.text import TextEntity
from .const import DOMAIN
from .system_settings import SystemSettingEntity


async def async_setup_entry(hass, entry, async_add_entities):
    if settings := hass.data[DOMAIN][entry.entry_id].get("system_settings"):
        async_add_entities([SignageName(settings)])


class SignageName(SystemSettingEntity, TextEntity):
    _attr_native_min = 1
    _attr_native_max = 32

    def __init__(self, settings):
        super().__init__(settings, "signageName", "signage_name", "mdi:rename-box")

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self.key)

    async def async_set_value(self, value):
        await self.coordinator.async_set(self.key, value)
