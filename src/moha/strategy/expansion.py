"""Volatility expansion engine — DESIGN.md §E.3, §G.3, §H.3."""
from __future__ import annotations

from typing import Optional

import numpy as np

from ..config import Config
from ..data.market_data import MarketData
from ..indicators import adx, atr, bollinger_width, ema, percentile_rank
from ..types import EngineName, EngineSignal, Side


class ExpansionEngine:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.p = cfg.strategy.expansion

    def evaluate(self, md: MarketData) -> Optional[EngineSignal]:
        m5 = md.primary
        m15 = md.context_mid
        if not m5.last_closed or not m15.last_closed:
            return None
        closes5 = m5.closes()
        if len(closes5) < self.p.bbwidth_window + 5:
            return None
        atr5 = atr(m5.highs(), m5.lows(), closes5, 14)
        atr_last = float(atr5[-1])
        if np.isnan(atr_last) or atr_last <= 0:
            return None

        bbw = bollinger_width(closes5, 20, 2.0)
        # Compression: at least `compressed_bars_needed` of the last
        # `lookback_compressed` bars had bbwidth percentile < threshold.
        pctiles = []
        for i in range(-self.p.lookback_compressed, 0):
            pctiles.append(percentile_rank(bbw[: len(bbw) + i + 1], self.p.bbwidth_window))
        pctiles_arr = np.array(pctiles)
        below = int(np.sum(pctiles_arr < self.p.bbwidth_pctile))
        if below < self.p.compressed_bars_needed:
            return None

        # Current bar's Bollinger bounds:
        window = closes5[-20:]
        mid = window.mean()
        std = window.std(ddof=0)
        upper = mid + 2 * std
        lower = mid - 2 * std

        trig = m5.last_closed
        vols = m5.volumes()
        vol_med = float(np.median(vols[-20:])) if len(vols) >= 20 else 0.0
        if vol_med <= 0 or trig.volume / vol_med < self.p.volume_mult:
            return None
        if trig.body_ratio < self.p.min_body_ratio:
            return None

        e21_15 = ema(m15.closes(), 21)
        adx_15 = adx(m15.highs(), m15.lows(), m15.closes(), 14)
        if np.isnan(e21_15[-1]) or np.isnan(adx_15[-1]):
            return None
        trend_up = m15.closes()[-1] > float(e21_15[-1])
        flat = adx_15[-1] <= 15

        side: Optional[Side] = None
        entry_ref = trig.close
        stop_ref = 0.0

        if trig.close > upper and (trend_up or flat):
            side = Side.LONG
            stop_ref = min(lower, entry_ref - 1.2 * atr_last)
        elif trig.close < lower and ((not trend_up) or flat):
            side = Side.SHORT
            stop_ref = max(upper, entry_ref + 1.2 * atr_last)
        else:
            return None

        risk = abs(entry_ref - stop_ref)
        if risk <= 0:
            return None
        tp1 = entry_ref + side.sign * self.p.tp1_r * risk
        tp2 = entry_ref + side.sign * self.p.tp2_r * risk

        vol_ratio = trig.volume / vol_med
        bbw_pct_now = percentile_rank(bbw, self.p.bbwidth_window)
        if np.isnan(bbw_pct_now):
            bbw_pct_now = 0.5
        score = max(0.0, min(1.0, 0.7 - bbw_pct_now + 0.3 * min(vol_ratio / 3.0, 1.0)))
        rr = abs(tp1 - entry_ref) / risk
        if rr < self.p.min_rr:
            return None

        return EngineSignal(
            engine=EngineName.EXPANSION,
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
            meta={"bbw_pctile": bbw_pct_now, "vol_ratio": vol_ratio},
        )
