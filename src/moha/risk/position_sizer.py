"""Position sizing — DESIGN.md §K."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class SymbolFilters:
    """Binance exchange info subset actually used by sizing."""
    tick_size: float
    step_size: float
    min_qty: float
    min_notional: float


def floor_to_step(x: float, step: float) -> float:
    if step <= 0:
        return x
    n = math.floor(x / step)
    return round(n * step, 10)


def round_price(x: float, tick: float) -> float:
    if tick <= 0:
        return x
    return round(round(x / tick) * tick, 10)


def size_position(
    equity: float,
    entry: float,
    stop: float,
    risk_pct: float,
    filters: SymbolFilters,
    max_effective_leverage: float,
) -> Optional[float]:
    """Return qty in BTC, or None if we can't build a valid order."""
    if equity <= 0 or entry <= 0 or risk_pct <= 0:
        return None
    stop_distance = abs(entry - stop)
    if stop_distance <= 0:
        return None
    risk_usdt = equity * risk_pct
    qty = risk_usdt / stop_distance

    # Leverage clamp.
    max_qty_from_lev = (equity * max_effective_leverage) / entry
    if qty > max_qty_from_lev:
        qty = max_qty_from_lev

    qty = floor_to_step(qty, filters.step_size)
    if qty < filters.min_qty:
        return None
    if qty * entry < filters.min_notional:
        return None

    # If rounding pushed *actual* risk >10% over target, drop one step.
    actual_risk = qty * stop_distance
    if actual_risk > 1.1 * risk_usdt and qty - filters.step_size >= filters.min_qty:
        qty = qty - filters.step_size
        if qty * entry < filters.min_notional:
            return None
    return qty


def leverage_cap_for_regime(regime_score: float, ladder: list) -> float:
    """Ladder from config: pick the first bracket whose `min <= score`.

    Ladder is expected sorted descending by `min`.
    """
    for br in ladder:
        if regime_score >= br.min:
            return br.max_lev
    return 1.0
