"""Price and favorable-phase parsing helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from .const import PRICE_TIME_KEYS, PRICE_VALUE_KEYS


@dataclass(frozen=True, slots=True)
class PriceSlot:
    """A timestamped electricity-price slot."""

    start: datetime
    price_eur_per_kwh: float


def parse_datetime(value: Any) -> datetime | None:
    """Parse a Home Assistant timestamp and normalize it to local time."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = dt_util.parse_datetime(value)
    else:
        return None

    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    return dt_util.as_local(parsed)


def _as_float(value: Any) -> float | None:
    """Convert a value to float without accepting booleans or non-finite data."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result or result in (float("inf"), float("-inf")):
        return None
    return result


def _walk_mappings(value: Any) -> Iterable[Mapping[str, Any]]:
    """Yield all nested mappings from arbitrary state attributes."""
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk_mappings(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _walk_mappings(child)


def collect_price_slots(*attribute_sets: Mapping[str, Any]) -> list[PriceSlot]:
    """Collect and deduplicate price slots from one or more attribute mappings."""
    by_start: dict[datetime, PriceSlot] = {}
    for attributes in attribute_sets:
        for item in _walk_mappings(attributes):
            start = None
            for key in PRICE_TIME_KEYS:
                if (
                    key in item
                    and (candidate := parse_datetime(item.get(key))) is not None
                ):
                    start = candidate
                    break
            if start is None:
                continue
            price = None
            for key in PRICE_VALUE_KEYS:
                if (
                    key in item
                    and (candidate_price := _as_float(item.get(key))) is not None
                ):
                    price = candidate_price
                    break
            if price is None:
                continue
            by_start[start] = PriceSlot(start=start, price_eur_per_kwh=price)
    return sorted(by_start.values(), key=lambda slot: slot.start)


def price_at(slots: list[PriceSlot], moment: datetime) -> float | None:
    """Return the price applicable at a requested moment.

    Slot boundaries are inferred from adjacent timestamps. For the last slot, the
    previous interval is reused; 15 minutes is used when no interval is available.
    """
    if not slots:
        return None

    target = dt_util.as_local(moment)
    intervals = [
        slots[index + 1].start - slots[index].start
        for index in range(len(slots) - 1)
        if slots[index + 1].start > slots[index].start
    ]
    nominal_interval = min(intervals) if intervals else timedelta(minutes=15)

    for index, slot in enumerate(slots):
        nominal_end = slot.start + nominal_interval
        if index + 1 < len(slots):
            end = min(slots[index + 1].start, nominal_end)
        else:
            end = nominal_end
        if slot.start <= target < end:
            return slot.price_eur_per_kwh
    return None


def current_state_price(state_value: str | None) -> float | None:
    """Parse the current numeric state of an ESC price sensor."""
    return _as_float(state_value)


def favorable_window(
    attributes: Mapping[str, Any],
) -> tuple[datetime, datetime | None] | None:
    """Extract the current or next favorable phase from ESC attributes."""
    start = parse_datetime(attributes.get("favorable_from"))
    if start is None:
        return None
    return start, parse_datetime(attributes.get("favorable_until"))
