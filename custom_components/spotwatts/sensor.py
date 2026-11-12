"""Sensors of a price area: the price now, the day's numbers and the cheapest windows ahead."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import SpotwattsConfigEntry
from .api import Interval
from .const import ATTRIBUTION, CONF_VAT, DOMAIN, WINDOW_HOURS
from .coordinator import Prices, SpotwattsCoordinator
from .prices import average, cheapest_window, current

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SpotwattsSensorDescription(SensorEntityDescription):
    value: Callable[[Prices, datetime], Interval | None] | None = None
    window_hours: int | None = None


DESCRIPTIONS: tuple[SpotwattsSensorDescription, ...] = (
    SpotwattsSensorDescription(key="price", translation_key="price", value=lambda p, now: current(p.intervals, now)),
    SpotwattsSensorDescription(
        key="today_average", translation_key="today_average", value=lambda p, _: average(p.today.intervals)
    ),
    SpotwattsSensorDescription(
        key="today_min",
        translation_key="today_min",
        value=lambda p, _: min(p.today.intervals, key=lambda item: item.price, default=None),
    ),
    SpotwattsSensorDescription(
        key="today_max",
        translation_key="today_max",
        value=lambda p, _: max(p.today.intervals, key=lambda item: item.price, default=None),
    ),
    SpotwattsSensorDescription(
        key="tomorrow_average",
        translation_key="tomorrow_average",
        value=lambda p, _: average(p.tomorrow.intervals) if p.tomorrow else None,
    ),
    *(
        SpotwattsSensorDescription(
            key=f"cheapest_{hours}h",
            translation_key=f"cheapest_{hours}h",
            device_class=SensorDeviceClass.TIMESTAMP,
            window_hours=hours,
        )
        for hours in WINDOW_HOURS
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: SpotwattsConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    vat = entry.options.get(CONF_VAT, True)
    async_add_entities(SpotwattsSensor(coordinator, description, vat) for description in DESCRIPTIONS)


class SpotwattsSensor(CoordinatorEntity[SpotwattsCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    # start/end change every quarter and the price lists are large: keep them out of the recorder
    _unrecorded_attributes = frozenset({"start", "end", "today", "tomorrow", "raw_today", "raw_tomorrow"})
    entity_description: SpotwattsSensorDescription

    def __init__(self, coordinator: SpotwattsCoordinator, description: SpotwattsSensorDescription, vat: bool) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._vat = vat
        self._window: Interval | None = None
        zone = coordinator.zone
        self._attr_unique_id = f"{zone}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, zone)},
            name=f"Spotwatts {zone}",
            manufacturer="Spotwatts",
            model="Day-ahead price area",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=coordinator.data.today.page,
        )
        if description.window_hours is None:
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_native_unit_of_measurement = coordinator.data.today.unit
            self._attr_suggested_display_precision = 4 if coordinator.data.today.unit.startswith("EUR") else 3

    def _item(self) -> Interval | None:
        now = dt_util.utcnow()
        hours = self.entity_description.window_hours
        if hours is None:
            return self.entity_description.value(self.coordinator.data, now)
        # A window that has begun is kept until it ends, so a time trigger on its start is not moved away
        if self._window is None or self._window.end <= now or self._window.start > now:
            self._window = cheapest_window(self.coordinator.data.intervals, now, hours)
        return self._window

    def _price(self, item: Interval) -> float:
        return round(item.price_vat if self._vat else item.price, 5)

    @property
    def native_value(self) -> float | datetime | None:
        item = self._item()
        if item is None:
            return None
        return item.start if self.entity_description.window_hours else self._price(item)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        item = self._item()
        if item is None:
            return None
        attributes: dict[str, Any] = {"start": item.start.isoformat(), "end": item.end.isoformat()}
        if self.entity_description.window_hours:
            attributes["average_price"] = self._price(item)
            attributes["unit"] = self.coordinator.data.today.unit
        if self.entity_description.key == "price":
            attributes.update(self._day_lists())
        return attributes

    def _day_lists(self) -> dict[str, Any]:
        """Today and tomorrow as plain lists and, for chart cards, as start/end/value like Nord Pool's sensor."""
        prices = self.coordinator.data
        tomorrow = prices.tomorrow.intervals if prices.tomorrow else []
        return {
            "vat_included": self._vat,
            "today": [self._price(item) for item in prices.today.intervals],
            "tomorrow": [self._price(item) for item in tomorrow],
            "tomorrow_valid": bool(tomorrow),
            "raw_today": [self._raw(item) for item in prices.today.intervals],
            "raw_tomorrow": [self._raw(item) for item in tomorrow],
        }

    def _raw(self, item: Interval) -> dict[str, Any]:
        return {"start": item.start.isoformat(), "end": item.end.isoformat(), "value": self._price(item)}
