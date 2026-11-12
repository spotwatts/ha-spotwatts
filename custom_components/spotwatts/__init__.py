"""The Spotwatts integration: day-ahead electricity prices of the Nordic and Baltic price areas."""

from __future__ import annotations

from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_utc_time_change

from .coordinator import SpotwattsCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type SpotwattsConfigEntry = ConfigEntry[SpotwattsCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SpotwattsConfigEntry) -> bool:
    coordinator = SpotwattsCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    @callback
    def _quarter(now: datetime) -> None:
        # The current price changes every quarter; after the zone's midnight the new day is put in place
        if coordinator.is_stale():
            entry.async_create_background_task(hass, coordinator.async_refresh(), f"spotwatts {coordinator.zone}")
        else:
            coordinator.async_update_listeners()

    entry.async_on_unload(async_track_utc_time_change(hass, _quarter, minute=(0, 15, 30, 45), second=1))
    entry.async_on_unload(entry.add_update_listener(_async_reload))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # True, not None: Home Assistant before 2026.11 expects a boolean
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SpotwattsConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: SpotwattsConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
