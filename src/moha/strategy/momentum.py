"""Momentum breakout engine — DESIGN.md §E.1, §G.1, §H.1."""
from __future__ import annotations

from typing import Optional

import numpy as np

from ..config import Config
from ..data.market_data import MarketData
from ..indicators import adx, atr, ema
from ..types import EngineName, EngineSignal, Side


class MomentumEngine:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.p = cfg.strategy.momentum

    def evaluate(self, md: MarketData) -> Optional[EngineSignal]:
        m5 = md.primary
        m15 = md.context_mid
        m1 = md.fast
        if not m5.last_closed or not m15.last_closed or not m1.last_closed:
            return None
        highs5, lows5, closes5, vols5 = m5.highs(), m5.lows(), m5.closes(), m5.volumes()
        if len(closes5) < self.p.lookback_bars + 5:
            return None
        atr5 = atr(highs5, lows5, closes5, 14)
        atr_last = float(atr5[-1])
        if np.isnan(atr_last) or atr_last <= 0:
            return None

        e21_15 = ema(m15.closes(), 21)
        e55_15 = ema(m15.closes(), 55)
        adx_15 = adx(m15.highs(), m15.lows(), m15.closes(), 14)
        if np.isnan(e21_15[-1]) or np.isnan(e55_15[-1]) or np.isnan(adx_15[-1]):
            return None
        adx_val = float(adx_15[-1])
        if adx_val < self.p.min_adx_15m:
            return None

        trig = m5.last_closed
        lookback = self.p.lookback_bars
        recent_highs = highs5[-(lookback + 1) : -1]
        recent_lows = lows5[-(lookback + 1) : -1]
        vol_med = float(np.median(vols5[-(lookback + 1) : -1])) if len(vols5) > lookback else 0.0
        if vol_med <= 0:
            return None
        vol_ratio = trig.volume / vol_med
        if vol_ratio < self.p.volume_mult:
            return None
        if trig.body_ratio < self.p.min_body_ratio:
            return None

        atr_pct = atr_last / trig.close
        side: Optional[Side] = None
        entry_ref = trig.close
        stop_ref = 0.0
        if (
            trig.close > recent_highs.max() * (1 + self.p.breakout_pct)
            and e21_15[-1] > e55_15[-1]
        ):
            side = Side.LONG
            stop_ref = trig.low - 0.15 * atr_last
        elif (
            trig.close < recent_lows.min() * (1 - self.p.breakout_pct)
            and e21_15[-1] < e55_15[-1]
        ):
            side = Side.SHORT
            stop_ref = trig.high + 0.15 * atr_last
        else:
            return None

        risk = abs(entry_ref - stop_ref)
        if risk <= 0:
            return None
        tp1 = entry_ref + side.sign * self.p.tp1_r * risk
        tp2 = entry_ref + side.sign * self.p.tp2_r * risk

        # Score in [0,1]. Bounded by ATR% "not stretched" and volume push.
        distance_ema = abs(trig.close - float(e55_15[-1])) / trig.close
        base = 0.5 + 0.5 * min(vol_ratio / 3.0, 1.0)
        score = max(0.0, min(1.0, base - 0.2 * distance_ema * 100.0))

        rr_tp1 = abs(tp1 - entry_ref) / risk
        if rr_tp1 < self.p.min_rr:
            return None

        return EngineSignal(
            engine=EngineName.MOMENTUM,
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
            meta={"vol_ratio": vol_ratio, "atr_pct": atr_pct, "adx_15m": adx_val},
        )
