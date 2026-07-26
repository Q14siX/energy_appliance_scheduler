"""Select platform for Energy Appliance Scheduler."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SchedulerConfigEntry
from .const import START_MODES
from .entity import ApplianceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SchedulerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up native start-mode and optional program selects."""
    for manager in entry.runtime_data.managers.values():
        entities: list[SelectEntity] = [ApplianceStartModeSelect(manager)]
        if manager.program_entity:
            entities.append(ApplianceProgramSelect(manager))
        async_add_entities(
            entities,
            config_subentry_id=manager.subentry.subentry_id,
        )


class ApplianceStartModeSelect(ApplianceEntity, SelectEntity):
    """Choose the next favorable phase or an exact timestamp."""

    _attr_translation_key = "start_mode"
    _attr_icon = "mdi:calendar-sync"
    _attr_options = list(START_MODES)

    def __init__(self, manager) -> None:
        super().__init__(manager, "start_mode")

    @property
    def current_option(self) -> str:
        return self.manager.state.mode

    async def async_select_option(self, option: str) -> None:
        await self.manager.async_set_mode(option)


class ApplianceProgramSelect(ApplianceEntity, SelectEntity):
    """Store the program that will be applied at the one-shot start."""

    _attr_translation_key = "program"
    _attr_icon = "mdi:washing-machine"

    def __init__(self, manager) -> None:
        super().__init__(manager, "program")

    @property
    def available(self) -> bool:
        return bool(self.manager.program_options)

    @property
    def options(self) -> list[str]:
        return self.manager.program_options

    @property
    def current_option(self) -> str | None:
        return self.manager.state.selected_program

    async def async_select_option(self, option: str) -> None:
        await self.manager.async_set_program(option)
