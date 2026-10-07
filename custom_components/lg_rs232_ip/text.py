"""Physical LG Signage name, independent of the HA device name."""

from homeassistant.components.text import TextEntity
from .const import DOMAIN
from .system_settings import SystemSettingEntity


async def async_setup_entry(hass, entry, async_add_entities):
    if settings := hass.data[DOMAIN][entry.entry_id].get("system_settings"):
        async_add_entities([SignageName(settings)])
    if maintenance := hass.data[DOMAIN][entry.entry_id].get("maintenance"):
        async_add_entities([NtpServer(maintenance)])


class NtpServer(SystemSettingEntity, TextEntity):
    _attr_native_min = 0
    _attr_native_max = 253

    def __init__(self, coordinator):
        super().__init__(coordinator, "ntp_server", "ntp_server", "mdi:server-network")

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self.key)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        return {"server_mode": data.get("ntpServerMode"), "automatic_time": data.get("clock_auto"), "empty_value_uses_default_server": True}

    async def async_set_value(self, value):
        await self.coordinator.async_set(self.key, value)


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
