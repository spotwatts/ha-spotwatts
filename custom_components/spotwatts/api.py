"""Client of the Spotwatts price API (https://spotwatts.com/en/api)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import aiohttp

from .const import API_BASE


class SpotwattsError(Exception):
    """The API could not be reached or answered with an error."""


@dataclass(frozen=True, slots=True)
class Interval:
    """A price interval or window, in the zone's currency per kWh."""

    start: datetime
    end: datetime
    price: float
    price_vat: float


@dataclass(frozen=True, slots=True)
class Day:
    """One delivery day of one zone."""

    date: date
    unit: str
    page: str
    intervals: list[Interval]


class SpotwattsClient:
    """Reads one zone-day per request."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def day(self, zone: str, day: date) -> Day | None:
        """Prices of the zone's local `day`; None while they are not published (404)."""
        # A dated URL, not "today": an edge cache never serves yesterday's prices for it after midnight
        url = f"{API_BASE}/{zone.lower()}/{day.isoformat()}.json"
        try:
            async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as response:
                if response.status == 404:
                    return None
                response.raise_for_status()
                data: dict[str, Any] = await response.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SpotwattsError(f"{url}: {err}") from err

        try:
            return Day(
                date=date.fromisoformat(data["date"]),
                unit=data["unit"],
                page=data.get("page", "https://spotwatts.com/"),
                intervals=[
                    Interval(
                        start=datetime.fromisoformat(item["start"]),
                        end=datetime.fromisoformat(item["end"]),
                        price=float(item["price"]),
                        price_vat=float(item["price_vat"]),
                    )
                    for item in data["intervals"]
                ],
            )
        except (KeyError, TypeError, ValueError) as err:
            raise SpotwattsError(f"{url}: unexpected answer ({err})") from err
