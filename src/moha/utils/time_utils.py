"""Time helpers. Bot NEVER uses time.time() for trading decisions.

Live and paper get 'now' from exchange timestamps. Backtest gets 'now'
from the current replayed bar. This module centralizes that convention.
"""
from __future__ import annotations

from datetime import datetime, timezone


def ms_to_dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def dt_to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def utc_hour(ms: int) -> int:
    return ms_to_dt(ms).hour


def is_weekend(ms: int) -> bool:
    """UTC weekend: Fri 22:00 through Mon 00:00.

    Roughly Sat / Sun in UTC; used only for risk scaling per DESIGN.md §C.
    """
    dt = ms_to_dt(ms)
    wd = dt.weekday()  # Mon=0..Sun=6
    if wd in (5, 6):
        return True
    if wd == 4 and dt.hour >= 22:
        return True
    return False


def session_name(ms: int) -> str:
    h = utc_hour(ms)
    if 0 <= h < 7:
        return "ASIA"
    if 7 <= h < 13:
        return "LONDON"
    if 13 <= h < 16:
        return "OVERLAP"
    if 16 <= h < 21:
        return "NY_PM"
    return "OFF"
