"""Sensor platform for Energy Appliance Scheduler."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SchedulerConfigEntry
from .const import STATUS_OPTIONS
from .entity import ApplianceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SchedulerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up native status, planned-start and price sensors."""
    for manager in entry.runtime_data.managers.values():
        async_add_entities(
            [
                ApplianceStatusSensor(manager),
                AppliancePlannedStartSensor(manager),
                AppliancePlannedPriceSensor(manager),
            ],
            config_subentry_id=manager.subentry.subentry_id,
        )


class ApplianceStatusSensor(ApplianceEntity, SensorEntity):
    """Expose scheduler state and diagnostics."""

    _attr_translation_key = "status"
    _attr_icon = "mdi:progress-clock"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(STATUS_OPTIONS)

    def __init__(self, manager) -> None:
        super().__init__(manager, "status")

    @property
    def native_value(self) -> str:
        return self.manager.state.status

    @property
    def extra_state_attributes(self):
        return {
            "start_authorized": self.manager.state.armed,
            "mode": self.manager.state.mode,
            "selected_program": self.manager.state.selected_program,
            "program_entity": self.manager.program_entity,
            "operating_state_entity": self.manager.operating_state_entity,
            "last_started": self.manager.state.last_started,
            "last_started_price_cents": self.manager.state.last_started_price_cents,
            "last_error": self.manager.state.last_error,
            "favorable_phase_sensor": self.manager.runtime.favorable_phase_sensor,
            "favorable_now_sensor": self.manager.runtime.favorable_now_sensor,
            "price_sensor": self.manager.runtime.price_sensor,
        }


class AppliancePlannedStartSensor(ApplianceEntity, SensorEntity):
    """Expose the calculated start timestamp."""

    _attr_translation_key = "planned_start"
    _attr_icon = "mdi:clock-start"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, manager) -> None:
        super().__init__(manager, "planned_start")

    @property
    def native_value(self):
        return self.manager.planned_start


class AppliancePlannedPriceSensor(ApplianceEntity, SensorEntity):
    """Expose the planned electricity price in ct/kWh."""

    _attr_translation_key = "planned_price"
    _attr_icon = "mdi:currency-eur"
    _attr_native_unit_of_measurement = "ct/kWh"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(self, manager) -> None:
        super().__init__(manager, "planned_price")

    @property
    def native_value(self) -> float | None:
        return self.manager.state.planned_price_cents
