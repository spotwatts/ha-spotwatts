"""Calculations on price intervals."""

from __future__ import annotations

from datetime import datetime, timedelta

from .api import Interval


def current(intervals: list[Interval], now: datetime) -> Interval | None:
    """The interval that contains `now`."""
    return next((item for item in intervals if item.start <= now < item.end), None)


def average(intervals: list[Interval]) -> Interval | None:
    """The intervals as one, priced at their time-weighted average (quarters and hours mix on some days)."""
    if not intervals:
        return None
    seconds = [(item.end - item.start).total_seconds() for item in intervals]
    total = sum(seconds)
    return Interval(
        start=intervals[0].start,
        end=intervals[-1].end,
        price=sum(item.price * s for item, s in zip(intervals, seconds, strict=True)) / total,
        price_vat=sum(item.price_vat * s for item, s in zip(intervals, seconds, strict=True)) / total,
    )


def cheapest_window(intervals: list[Interval], not_before: datetime, hours: int) -> Interval | None:
    """Cheapest continuous `hours`-hour window starting at `not_before` or later; the earliest wins ties.

    None when the known prices do not reach that far.
    """
    length = timedelta(hours=hours)
    upcoming = [item for item in intervals if item.start >= not_before]
    best: Interval | None = None
    for i, first in enumerate(upcoming):
        run: list[Interval] = []
        for item in upcoming[i:]:
            if run and item.start != run[-1].end:
                break
            run.append(item)
            if item.end - first.start >= length:
                break
        if run[-1].end - first.start != length:
            continue
        window = average(run)
        if best is None or window.price < best.price:
            best = window
    return best
