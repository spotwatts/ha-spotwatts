"""Calculations on intervals."""

from datetime import UTC, datetime, timedelta

from custom_components.spotwatts.api import Interval
from custom_components.spotwatts.prices import average, cheapest_window, current

T0 = datetime(2026, 11, 12, 0, 0, tzinfo=UTC)


def quarters(prices: list[float], start: datetime = T0, minutes: int = 15) -> list[Interval]:
    step = timedelta(minutes=minutes)
    return [Interval(start + i * step, start + (i + 1) * step, p, p * 1.25) for i, p in enumerate(prices)]


def test_current_is_the_interval_containing_now():
    items = quarters([1, 2, 3])
    assert current(items, T0 + timedelta(minutes=16)).price == 2
    assert current(items, T0 + timedelta(minutes=15)).price == 2
    assert current(items, T0 + timedelta(minutes=45)) is None


def test_average_is_weighted_by_time():
    # An hour at 4 and a quarter at 0, as on the day hourly prices turned into quarters
    items = quarters([4], minutes=60) + quarters([0], start=T0 + timedelta(hours=1))
    assert average(items).price == 4 * 60 / 75
    assert average([]) is None


def test_cheapest_window_starts_now_or_later_and_the_earliest_wins_ties():
    items = quarters([1, 1, 1, 1] + [5] * 4 + [2, 2, 2, 2] + [2, 2, 2, 2])
    window = cheapest_window(items, T0, 1)
    assert (window.start, window.end, window.price) == (T0, T0 + timedelta(hours=1), 1)

    # Only windows that start at or after the given moment: never one already under way
    later = cheapest_window(items, T0 + timedelta(minutes=5), 1)
    assert later.start == T0 + timedelta(minutes=15)
    assert later.price == (1 + 1 + 1 + 5) / 4

    assert cheapest_window(items, T0 + timedelta(hours=2, minutes=1), 2) is None


def test_cheapest_window_never_bridges_a_gap():
    items = quarters([1] * 4) + quarters([1] * 4, start=T0 + timedelta(hours=2))
    assert cheapest_window(items, T0, 2) is None
