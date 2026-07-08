"""Pullback continuation engine — DESIGN.md §E.2, §G.2, §H.2."""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from ..config import Config
from ..data.market_data import MarketData
from ..indicators import atr, ema, rsi
from ..types import EngineName, EngineSignal, Side


def _last_swing(highs: np.ndarray, lows: np.ndarray, lookback: int = 30) -> Tuple[float, float]:
    """Return (swing_low, swing_high) over the last `lookback` bars."""
    lb = min(lookback, len(highs))
    return float(lows[-lb:].min()), float(highs[-lb:].max())


def _last_higher_low(lows: np.ndarray, ema21: np.ndarray, lookback: int = 30) -> Optional[float]:
    """Very simple higher-low pivot: last local low above the EMA."""
    lb = min(lookback, len(lows))
    piv: Optional[float] = None
    for i in range(len(lows) - lb + 1, len(lows) - 1):
        if i < 2:
            continue
        if lows[i] < lows[i - 1] and lows[i] < lows[i + 1] and lows[i] > (ema21[i] if not np.isnan(ema21[i]) else -np.inf):
            piv = float(lows[i])
    return piv


def _last_lower_high(highs: np.ndarray, ema21: np.ndarray, lookback: int = 30) -> Optional[float]:
    lb = min(lookback, len(highs))
    piv: Optional[float] = None
    for i in range(len(highs) - lb + 1, len(highs) - 1):
        if i < 2:
            continue
        if highs[i] > highs[i - 1] and highs[i] > highs[i + 1] and highs[i] < (ema21[i] if not np.isnan(ema21[i]) else np.inf):
            piv = float(highs[i])
    return piv


class PullbackEngine:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.p = cfg.strategy.pullback

    def evaluate(self, md: MarketData) -> Optional[EngineSignal]:
        m5 = md.primary
        m15 = md.context_mid
        h1 = md.context_high
        if not m5.last_closed or not m15.last_closed or not h1.last_closed:
            return None
        closes5 = m5.closes()
        if len(closes5) < 60:
            return None
        atr5 = atr(m5.highs(), m5.lows(), closes5, 14)
        atr_last = float(atr5[-1])
        if np.isnan(atr_last) or atr_last <= 0:
            return None

        e21_5 = ema(closes5, 21)
        e21_15 = ema(m15.closes(), 21)
        e55_15 = ema(m15.closes(), 55)
        e21_1h = ema(h1.closes(), 21)
        e55_1h = ema(h1.closes(), 55)
        r5 = rsi(closes5, 14)
        if any(np.isnan(x[-1]) for x in [e21_5, e21_15, e55_15, e21_1h, e55_1h, r5]):
            return None

        trig = m5.last_closed
        s_lo, s_hi = _last_swing(m5.highs(), m5.lows(), 30)
        rng = s_hi - s_lo
        if rng <= 0:
            return None

        long_context = e21_1h[-1] > e55_1h[-1] and e21_15[-1] > e55_15[-1]
        short_context = e21_1h[-1] < e55_1h[-1] and e21_15[-1] < e55_15[-1]

        side: Optional[Side] = None
        stop_ref = 0.0
        entry_ref = trig.close

        if long_context:
            retrace = (s_hi - trig.low) / rng
            touch_ema = abs(trig.low - float(e21_5[-1])) / trig.close < 0.001
            fib_ok = self.p.fib_low <= retrace <= self.p.fib_high
            pivot_low = _last_higher_low(m5.lows(), e21_5, 30)
            higher_low_ok = pivot_low is not None and trig.low >= pivot_low
            rsi_ok = r5[-2] < 40 and r5[-1] >= 40
            bullish = trig.is_bull and trig.lower_wick / trig.range >= 0.3
            if (touch_ema or fib_ok) and higher_low_ok and rsi_ok and bullish:
                side = Side.LONG
                stop_ref = (pivot_low if pivot_low is not None else trig.low) - 0.2 * atr_last

        if side is None and short_context:
            retrace = (trig.high - s_lo) / rng
            touch_ema = abs(trig.high - float(e21_5[-1])) / trig.close < 0.001
            fib_ok = self.p.fib_low <= retrace <= self.p.fib_high
            pivot_high = _last_lower_high(m5.highs(), e21_5, 30)
            lower_high_ok = pivot_high is not None and trig.high <= pivot_high
            rsi_ok = r5[-2] > 60 and r5[-1] <= 60
            bearish = (not trig.is_bull) and trig.upper_wick / trig.range >= 0.3
            if (touch_ema or fib_ok) and lower_high_ok and rsi_ok and bearish:
                side = Side.SHORT
                stop_ref = (pivot_high if pivot_high is not None else trig.high) + 0.2 * atr_last

        if side is None:
            return None

        risk = abs(entry_ref - stop_ref)
        if risk <= 0:
            return None
        tp1 = entry_ref + side.sign * self.p.tp1_r * risk
        tp2 = entry_ref + side.sign * self.p.tp2_r * risk
        # Score by 15m ADX-lite: EMA gap normalized.
        gap = abs(e21_15[-1] - e55_15[-1]) / float(e55_15[-1])
        score = max(0.0, min(1.0, 0.6 + 0.4 * min(gap * 50.0, 1.0)))
        rr = abs(tp1 - entry_ref) / risk
        if rr < self.p.min_rr:
            return None

        return EngineSignal(
            engine=EngineName.PULLBACK,
            side=side,
            entry_ref=entry_ref,
            stop_ref=stop_ref,
            tp1_ref=tp1,
            tp2_ref=tp2,
            score=score,
            tp1_close_frac=self.p.tp1_close_frac,
            trail_atr_mult=self.p.trail_atr_mult,
            time_stop_bars=self.p.time_stop_bars,
            min_rr=self.p.min_rr,
            meta={"rsi_5m": float(r5[-1]), "atr_5m": atr_last},
        )
