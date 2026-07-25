"""Base entities for Energy Appliance Scheduler."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER, MODEL
from .runtime import ApplianceManager


class ApplianceEntity(Entity):
    """Base entity attached to an appliance config subentry."""

    _attr_has_entity_name = True

    def __init__(self, manager: ApplianceManager, key: str) -> None:
        self.manager = manager
        self._attr_unique_id = f"{manager.subentry.subentry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, manager.subentry.subentry_id)},
            name=manager.name,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to runtime updates."""
        await super().async_added_to_hass()
        self.async_on_remove(self.manager.add_listener(self.async_write_ha_state))
