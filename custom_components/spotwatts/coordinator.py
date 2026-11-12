"""Today's and tomorrow's prices of one zone."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import Day, Interval, SpotwattsClient, SpotwattsError
from .const import AUCTION_RESULTS, AUCTION_TZ, CONF_ZONE, DOMAIN, UPDATE_INTERVAL, ZONES

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Prices:
    today: Day
    tomorrow: Day | None

    @property
    def intervals(self) -> list[Interval]:
        """Today and tomorrow in one list: windows may run past midnight."""
        return self.today.intervals + (self.tomorrow.intervals if self.tomorrow else [])


class SpotwattsCoordinator(DataUpdateCoordinator[Prices]):
    """Requests a day only while it is missing: today once a day, tomorrow from the auction until published."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.zone: str = entry.data[CONF_ZONE]
        self.timezone = ZoneInfo(ZONES[self.zone])
        self._client = SpotwattsClient(async_get_clientsession(hass))
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=f"{DOMAIN} {self.zone}", update_interval=UPDATE_INTERVAL
        )

    def local_date(self, now: datetime | None = None) -> date:
        return (now or dt_util.utcnow()).astimezone(self.timezone).date()

    def is_stale(self) -> bool:
        """True after the zone's midnight until today's prices are in place."""
        return self.data is not None and self.data.today.date != self.local_date()

    async def _async_update_data(self) -> Prices:
        now = dt_util.utcnow()
        today = self.local_date(now)
        tomorrow = today + timedelta(days=1)
        known = [day for day in (self.data.today, self.data.tomorrow) if day] if self.data else []

        today_prices = next((day for day in known if day.date == today), None)
        if today_prices is None:
            try:
                today_prices = await self._client.day(self.zone, today)
            except SpotwattsError as err:
                raise UpdateFailed(str(err)) from err
            if today_prices is None:
                raise UpdateFailed(f"No prices for {self.zone} on {today} yet")

        tomorrow_prices = next((day for day in known if day.date == tomorrow), None)
        auction = now.astimezone(AUCTION_TZ)
        if tomorrow_prices is None and (auction.hour, auction.minute) >= AUCTION_RESULTS:
            try:
                tomorrow_prices = await self._client.day(self.zone, tomorrow)
            except SpotwattsError as err:
                # Today's prices stay valid; tomorrow is asked for again on the next update
                _LOGGER.debug("Tomorrow's prices for %s not fetched: %s", self.zone, err)

        return Prices(today=today_prices, tomorrow=tomorrow_prices)
