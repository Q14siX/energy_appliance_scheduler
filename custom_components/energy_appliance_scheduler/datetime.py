"""DateTime platform for Energy Appliance Scheduler."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SchedulerConfigEntry
from .entity import ApplianceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SchedulerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one exact-start datetime entity per appliance."""
    for manager in entry.runtime_data.managers.values():
        async_add_entities(
            [ApplianceStartDateTime(manager)],
            config_subentry_id=manager.subentry.subentry_id,
        )


class ApplianceStartDateTime(ApplianceEntity, DateTimeEntity):
    """User-selected exact start timestamp."""

    _attr_translation_key = "fixed_start_time"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, manager) -> None:
        super().__init__(manager, "fixed_start_time")

    @property
    def native_value(self) -> datetime | None:
        return self.manager.scheduled_time

    async def async_set_value(self, value: datetime) -> None:
        await self.manager.async_set_scheduled_time(value)
