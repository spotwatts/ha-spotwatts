"""Shared fixtures: API answers built from a list of quarter prices."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

API = "https://spotwatts.com/api/v1"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components/spotwatts in every test."""
    yield


def day_json(
    zone: str, date: str, prices: list[float], tz: str = "Europe/Stockholm", vat: float = 25.0
) -> dict[str, Any]:
    """An API day body: `prices` are consecutive quarters from the local midnight (excl. VAT, per kWh)."""
    start = datetime.fromisoformat(date).replace(tzinfo=ZoneInfo(tz))
    intervals = []
    for i, price in enumerate(prices):
        begin = start + timedelta(minutes=15 * i)
        intervals.append(
            {
                "start": begin.isoformat(),
                "end": (begin + timedelta(minutes=15)).isoformat(),
                "price": price,
                "price_vat": round(price * (1 + vat / 100), 5),
                "eur_mwh": price * 100,
            }
        )
    return {
        "zone": zone,
        "date": date,
        "timezone": tz,
        "currency": "SEK",
        "unit": "SEK/kWh",
        "vat_rate": vat,
        "page": f"https://spotwatts.com/se/{zone.lower()}",
        "intervals": intervals,
    }
