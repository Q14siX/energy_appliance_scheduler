"""Binary sensor platform for Energy Appliance Scheduler."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SchedulerConfigEntry
from .entity import ApplianceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SchedulerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one optional operating-state mirror per appliance."""
    for manager in entry.runtime_data.managers.values():
        if not manager.operating_state_entity:
            continue
        async_add_entities(
            [ApplianceOperatingBinarySensor(manager)],
            config_subentry_id=manager.subentry.subentry_id,
        )


class ApplianceOperatingBinarySensor(ApplianceEntity, BinarySensorEntity):
    """Expose whether the configured operating-state entity means running."""

    _attr_translation_key = "operating"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:progress-check"

    def __init__(self, manager) -> None:
        super().__init__(manager, "operating")

    @property
    def available(self) -> bool:
        source = self.hass.states.get(self.manager.operating_state_entity)
        return source is not None and source.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)

    @property
    def is_on(self) -> bool:
        return self.manager.is_running()

    @property
    def extra_state_attributes(self):
        return {
            "source_entity": self.manager.operating_state_entity,
            "running_states": sorted(self.manager.running_states),
        }
