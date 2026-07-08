"""Numeric indicators used by all engines.

All functions operate on closed candles. No lookahead. Each function
returns a numpy array of the same length as the input, with leading
NaNs for the warmup period.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np


def _to_array(x: Sequence[float]) -> np.ndarray:
    return np.asarray(x, dtype=np.float64)


def sma(values: Sequence[float], period: int) -> np.ndarray:
    v = _to_array(values)
    out = np.full_like(v, np.nan)
    if period <= 0 or len(v) < period:
        return out
    cs = np.cumsum(v)
    out[period - 1] = cs[period - 1] / period
    out[period:] = (cs[period:] - cs[:-period]) / period
    return out


def ema(values: Sequence[float], period: int) -> np.ndarray:
    v = _to_array(values)
    n = len(v)
    out = np.full(n, np.nan)
    if n == 0 or period <= 0:
        return out
    k = 2.0 / (period + 1)
    # Seed with SMA of the first `period` values for stability.
    if n < period:
        return out
    seed = v[:period].mean()
    out[period - 1] = seed
    for i in range(period, n):
        out[i] = v[i] * k + out[i - 1] * (1 - k)
    return out


def rsi(closes: Sequence[float], period: int = 14) -> np.ndarray:
    c = _to_array(closes)
    n = len(c)
    out = np.full(n, np.nan)
    if n < period + 1:
        return out
    delta = np.diff(c)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    # Wilder's smoothing
    avg_gain = gain[:period].mean()
    avg_loss = loss[:period].mean()
    out[period] = 100 - (100 / (1 + (avg_gain / avg_loss if avg_loss > 0 else np.inf)))
    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gain[i - 1]) / period
        avg_loss = (avg_loss * (period - 1) + loss[i - 1]) / period
        rs = avg_gain / avg_loss if avg_loss > 0 else np.inf
        out[i] = 100 - (100 / (1 + rs))
    return out


def true_range(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float]) -> np.ndarray:
    h = _to_array(highs)
    l = _to_array(lows)  # noqa: E741
    c = _to_array(closes)
    n = len(h)
    tr = np.zeros(n)
    if n == 0:
        return tr
    tr[0] = h[0] - l[0]
    for i in range(1, n):
        tr[i] = max(
            h[i] - l[i],
            abs(h[i] - c[i - 1]),
            abs(l[i] - c[i - 1]),
        )
    return tr


def atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> np.ndarray:
    tr = true_range(highs, lows, closes)
    n = len(tr)
    out = np.full(n, np.nan)
    if n < period:
        return out
    seed = tr[:period].mean()
    out[period - 1] = seed
    for i in range(period, n):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def adx(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> np.ndarray:
    """Wilder's Average Directional Index."""
    h = _to_array(highs)
    l = _to_array(lows)  # noqa: E741
    c = _to_array(closes)
    n = len(h)
    out = np.full(n, np.nan)
    if n < 2 * period:
        return out

    up_move = np.diff(h)
    dn_move = -np.diff(l)
    plus_dm = np.where((up_move > dn_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((dn_move > up_move) & (dn_move > 0), dn_move, 0.0)
    tr = true_range(h, l, c)

    # Wilder's smoothed sums (align with position i in the closes array).
    atr_w = np.zeros(n)
    plus_dm_w = np.zeros(n)
    minus_dm_w = np.zeros(n)

    atr_w[period] = tr[1 : period + 1].sum()
    plus_dm_w[period] = plus_dm[:period].sum()
    minus_dm_w[period] = minus_dm[:period].sum()

    for i in range(period + 1, n):
        atr_w[i] = atr_w[i - 1] - (atr_w[i - 1] / period) + tr[i]
        plus_dm_w[i] = plus_dm_w[i - 1] - (plus_dm_w[i - 1] / period) + plus_dm[i - 1]
        minus_dm_w[i] = minus_dm_w[i - 1] - (minus_dm_w[i - 1] / period) + minus_dm[i - 1]

    dx = np.zeros(n)
    for i in range(period, n):
        if atr_w[i] <= 0:
            continue
        plus_di = 100 * plus_dm_w[i] / atr_w[i]
        minus_di = 100 * minus_dm_w[i] / atr_w[i]
        s = plus_di + minus_di
        dx[i] = 100 * abs(plus_di - minus_di) / s if s > 0 else 0.0

    # Average DX with Wilder smoothing (period).
    if n < 2 * period:
        return out
    seed = dx[period : 2 * period].mean()
    out[2 * period - 1] = seed
    for i in range(2 * period, n):
        out[i] = (out[i - 1] * (period - 1) + dx[i]) / period
    return out


def bollinger_width(closes: Sequence[float], period: int = 20, k: float = 2.0) -> np.ndarray:
    """Bollinger band width normalized by mid, as a fraction (e.g. 0.02 = 2%)."""
    c = _to_array(closes)
    n = len(c)
    out = np.full(n, np.nan)
    if n < period:
        return out
    for i in range(period - 1, n):
        window = c[i - period + 1 : i + 1]
        mid = window.mean()
        std = window.std(ddof=0)
        upper = mid + k * std
        lower = mid - k * std
        if mid > 0:
            out[i] = (upper - lower) / mid
    return out


def percentile_rank(series: Sequence[float], window: int, value: float | None = None) -> float:
    """Return the percentile rank of the *last* value in the last `window` values.

    Returns NaN if there is insufficient history.
    """
    v = _to_array(series)
    if len(v) < window:
        return float("nan")
    tail = v[-window:]
    tail = tail[~np.isnan(tail)]
    if len(tail) == 0:
        return float("nan")
    target = tail[-1] if value is None else value
    return float((tail <= target).mean())
