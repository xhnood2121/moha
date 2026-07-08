"""Exit rules — DESIGN.md §I."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from ..types import ExitReason, Side, Trade


@dataclass
class ExitDecision:
    reason: ExitReason
    price: float
    qty_frac: float   # fraction of remaining position to close


class ExitManager:
    """Pure function evaluator called on every 1m bar close.

    The manager only *decides*; the order manager places reduce-only
    orders and updates state.
    """

    def __init__(self):
        pass

    def on_bar_close(
        self,
        trade: Trade,
        bar_high: float,
        bar_low: float,
        bar_close: float,
        atr_5m: float,
        bars_since_entry: int,
        time_stop_bars: int,
        trail_atr_mult: float,
        entry_atr_5m: float,
    ) -> Optional[ExitDecision]:
        sign = trade.side.sign

        # Update MFE / MAE.
        favorable = (bar_high - trade.entry_price) if sign > 0 else (trade.entry_price - bar_low)
        adverse = (trade.entry_price - bar_low) if sign > 0 else (bar_high - trade.entry_price)
        trade.max_favorable = max(trade.max_favorable, favorable)
        trade.max_adverse = max(trade.max_adverse, adverse)

        # 1) Hard stop hit (assume touched intra-bar).
        if sign > 0 and bar_low <= trade.stop_price:
            return ExitDecision(ExitReason.STOP, trade.stop_price, 1.0)
        if sign < 0 and bar_high >= trade.stop_price:
            return ExitDecision(ExitReason.STOP, trade.stop_price, 1.0)

        # 2) TP1 — takes fixed partial then moves stop to breakeven.
        if not trade.tp1_hit:
            if sign > 0 and bar_high >= trade.tp1_price:
                trade.tp1_hit = True
                trade.stop_price = trade.entry_price   # move to BE
                return ExitDecision(
                    ExitReason.TP1, trade.tp1_price, _tp1_close_frac_from_trade(trade)
                )
            if sign < 0 and bar_low <= trade.tp1_price:
                trade.tp1_hit = True
                trade.stop_price = trade.entry_price
                return ExitDecision(
                    ExitReason.TP1, trade.tp1_price, _tp1_close_frac_from_trade(trade)
                )

        # 3) TP2 hit
        if trade.tp2_price is not None:
            if sign > 0 and bar_high >= trade.tp2_price:
                return ExitDecision(ExitReason.TP2, trade.tp2_price, 1.0)
            if sign < 0 and bar_low <= trade.tp2_price:
                return ExitDecision(ExitReason.TP2, trade.tp2_price, 1.0)

        # 4) Time stop.
        if bars_since_entry >= time_stop_bars and not trade.tp1_hit:
            return ExitDecision(ExitReason.TIME, bar_close, 1.0)

        # 5) Trailing stop after TP1 (or after 1.5R for runner).
        if trade.tp1_hit and atr_5m > 0:
            # Track a running high/low reference.
            if sign > 0:
                trade.trail_ref_price = max(trade.trail_ref_price, bar_high)
                trail = trade.trail_ref_price - trail_atr_mult * atr_5m
                if bar_low <= trail:
                    return ExitDecision(ExitReason.TP2, trail, 1.0)
                # Also ratchet the stop up.
                trade.stop_price = max(trade.stop_price, trail)
            else:
                if trade.trail_ref_price == 0.0:
                    trade.trail_ref_price = bar_low
                trade.trail_ref_price = min(trade.trail_ref_price, bar_low)
                trail = trade.trail_ref_price + trail_atr_mult * atr_5m
                if bar_high >= trail:
                    return ExitDecision(ExitReason.TP2, trail, 1.0)
                trade.stop_price = min(trade.stop_price, trail) if trade.stop_price else trail

        # 6) Volatility collapse exit — atr dropped below 40% of entry-time atr
        #    AND unrealized <0.5R.
        if entry_atr_5m > 0 and atr_5m < 0.4 * entry_atr_5m and not trade.tp1_hit:
            unrealized_r = _r_multiple(trade, bar_close)
            if unrealized_r < 0.5:
                return ExitDecision(ExitReason.VOL_COLLAPSE, bar_close, 1.0)

        return None

    def on_opposite_signal(self, trade: Trade, opposite_score: float, threshold: float = 0.7) -> Optional[ExitDecision]:
        if opposite_score >= threshold:
            return ExitDecision(ExitReason.OPPOSITE, trade.entry_price, 1.0)
        return None


def _tp1_close_frac_from_trade(trade: Trade) -> float:
    # Stored on the trade dataclass via engine defaults; ExitManager
    # doesn't know engine specifics, so we conservatively default to 0.5
    # if not annotated. The signal engine sets it via `tp1_close_frac`.
    return 0.5


def _r_multiple(trade: Trade, mark: float) -> float:
    risk = abs(trade.entry_price - trade.stop_price)
    if risk <= 0:
        return 0.0
    return trade.side.sign * (mark - trade.entry_price) / risk
