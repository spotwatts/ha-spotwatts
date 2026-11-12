"""Constants of the Spotwatts integration."""

from datetime import timedelta
from typing import Final
from zoneinfo import ZoneInfo

DOMAIN: Final = "spotwatts"

API_BASE: Final = "https://spotwatts.com/api/v1"

CONF_ZONE: Final = "zone"
CONF_VAT: Final = "vat"

# Price area → timezone of its delivery day
ZONES: Final[dict[str, str]] = {
    "NO1": "Europe/Oslo",
    "NO2": "Europe/Oslo",
    "NO3": "Europe/Oslo",
    "NO4": "Europe/Oslo",
    "NO5": "Europe/Oslo",
    "SE1": "Europe/Stockholm",
    "SE2": "Europe/Stockholm",
    "SE3": "Europe/Stockholm",
    "SE4": "Europe/Stockholm",
    "DK1": "Europe/Copenhagen",
    "DK2": "Europe/Copenhagen",
    "FI": "Europe/Helsinki",
    "EE": "Europe/Tallinn",
    "LT": "Europe/Vilnius",
    "LV": "Europe/Riga",
}

# Only polled while tomorrow is missing after the auction; otherwise no request is made
UPDATE_INTERVAL: Final = timedelta(minutes=15)

# The SDAC auction closes at 12:00 CET and publishes at about 12:45 CET, for every zone
AUCTION_TZ: Final = ZoneInfo("Europe/Berlin")
AUCTION_RESULTS: Final = (12, 45)

WINDOW_HOURS: Final = (1, 2, 3, 4)

ATTRIBUTION: Final = "Prices: Spotwatts (spotwatts.com), data from ENTSO-E"
