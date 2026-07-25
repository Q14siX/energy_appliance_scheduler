"""Diagnostics support for Energy Appliance Scheduler."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from . import SchedulerConfigEntry
from .const import (
    ALEXA_TEXT_KEYS,
    CONF_PREPARE_ACTIONS,
    CONF_START_ACTIONS,
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SchedulerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics without exposing arbitrary action payloads or spoken texts."""
    entry_data = {
        key: value
        for key, value in (dict(entry.data) | dict(entry.options)).items()
        if key not in ALEXA_TEXT_KEYS
    }
    return {
        "entry": entry_data,
        "appliances": {
            manager.name: {
                "subentry_id": manager.subentry.subentry_id,
                "icon": manager.icon,
                "program_entity": manager.program_entity,
                "program_behavior": manager.program_behavior,
                "operating_state_entity": manager.operating_state_entity,
                "running_states": sorted(manager.running_states),
                "confirmation_timeout": manager.confirmation_timeout,
                "prepare_action_count": len(
                    manager.subentry.data.get(CONF_PREPARE_ACTIONS, [])
                ),
                "start_action_count": len(
                    manager.subentry.data.get(CONF_START_ACTIONS, [])
                ),
                "state": asdict(manager.state),
            }
            for manager in entry.runtime_data.managers.values()
        },
    }
