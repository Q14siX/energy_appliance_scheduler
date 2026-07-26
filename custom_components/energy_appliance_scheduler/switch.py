"""Switch platform for Energy Appliance Scheduler."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SchedulerConfigEntry
from .entity import ApplianceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SchedulerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up native appliance control switches."""
    for manager in entry.runtime_data.managers.values():
        async_add_entities(
            [
                ApplianceArmedSwitch(manager),
                ApplianceAlexaQuietHoursOverrideSwitch(manager),
            ],
            config_subentry_id=manager.subentry.subentry_id,
        )


class ApplianceArmedSwitch(ApplianceEntity, SwitchEntity):
    """Explicit user confirmation that authorizes exactly one start."""

    _attr_translation_key = "start_authorization"
    _attr_icon = "mdi:play-circle-outline"

    def __init__(self, manager) -> None:
        super().__init__(manager, "start_authorization")

    @property
    def is_on(self) -> bool:
        return self.manager.state.armed

    async def async_turn_on(self, **kwargs) -> None:
        await self.manager.async_set_armed(True, context=self._context)

    async def async_turn_off(self, **kwargs) -> None:
        await self.manager.async_set_armed(False, context=self._context)


class ApplianceAlexaQuietHoursOverrideSwitch(ApplianceEntity, SwitchEntity):
    """Allow Alexa messages for one appliance during the global quiet hours."""

    _attr_translation_key = "alexa_quiet_hours_override"
    _attr_icon = "mdi:volume-high"

    def __init__(self, manager) -> None:
        super().__init__(manager, "alexa_quiet_hours_override")

    @property
    def is_on(self) -> bool:
        return self.manager.alexa_quiet_hours_override

    async def async_turn_on(self, **kwargs) -> None:
        await self.manager.async_set_alexa_quiet_hours_override(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.manager.async_set_alexa_quiet_hours_override(False)
