"""Display app controls on the HA device page."""

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .picture_settings import PictureSettingEntity, PICTURE_ACTIONS


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    if picture := data.get("picture_settings"):
        async_add_entities([PictureActionButton(picture, key) for key in sorted(PICTURE_ACTIONS)])
    manager = data.get("display_app")
    if manager is None:
        return
    keys = ["restore_si"]
    if manager.enabled:
        keys += ["test_display_app", "display_app_dashboard"]
        if manager.resident:
            keys += ["resume_display_app", "refresh_platform"]
    async_add_entities([DisplayAppButton(manager, entry, key) for key in keys])


class PictureActionButton(PictureSettingEntity, ButtonEntity):
    async def async_press(self):
        await self.coordinator.async_action(self.key)


class DisplayAppButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:monitor-dashboard"

    def __init__(self, manager, entry, key):
        self.manager, self.key = manager, key
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}}
        if key == "refresh_platform":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        if key == "restore_si":
            self._attr_entity_category = EntityCategory.CONFIG

    async def async_press(self):
        if self.key == "restore_si":
            await self.manager.async_restore_si()
        elif self.key == "refresh_platform":
            await self.manager.platform.refresh()
        elif self.key == "resume_display_app":
            await self.manager.async_resume()
        else:
            await self.manager.controller.async_show_display_app(
                title="Home Assistant",
                message="Display-App: Verbindung erfolgreich"
                if self.key == "test_display_app"
                else "",
                dashboard=self.key == "display_app_dashboard",
                duration=15 if self.key == "test_display_app" else 60,
            )
