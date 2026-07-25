"""Energy Appliance Scheduler integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .runtime import SchedulerRuntime


type SchedulerConfigEntry = ConfigEntry[SchedulerRuntime]


async def async_setup_entry(hass: HomeAssistant, entry: SchedulerConfigEntry) -> bool:
    """Set up Energy Appliance Scheduler from one config entry."""
    runtime = SchedulerRuntime(hass, entry)
    await runtime.async_setup()
    entry.runtime_data = runtime
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: SchedulerConfigEntry
) -> None:
    """Reload when options or appliance subentries change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(
    hass: HomeAssistant, entry: SchedulerConfigEntry
) -> bool:
    """Migrate the first package version without losing configured devices."""
    if entry.version < 2:
        hass.config_entries.async_update_entry(entry, version=2)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SchedulerConfigEntry) -> bool:
    """Unload an Energy Appliance Scheduler config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_unload()
    return unloaded
