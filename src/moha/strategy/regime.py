"""Regime detection & engine router — see DESIGN.md §E.4."""
from __future__ import annotations

from typing import Optional

import numpy as np

from ..config import Config
from ..data.market_data import MarketData
from ..indicators import adx, bollinger_width, ema, percentile_rank
from ..types import EngineName, RegimeSnapshot
from ..utils.time_utils import is_weekend, session_name


class RegimeRouter:
    """Turn market state into a `RegimeSnapshot` and pick an engine."""

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def classify(self, md: MarketData, now_ms: int) -> Optional[RegimeSnapshot]:
        h1 = md.context_high
        m15 = md.context_mid
        m5 = md.primary
        if not h1.last_closed or not m15.last_closed or not m5.last_closed:
            return None
        if len(h1.closes()) < 60 or len(m15.closes()) < 30 or len(m5.closes()) < 45:
            return None

        # 1h EMA slope
        c1h = h1.closes()
        e21 = ema(c1h, 21)
        e55 = ema(c1h, 55)
        if np.isnan(e21[-1]) or np.isnan(e55[-1]):
            return None
        ema_diff_pct = (e21[-1] - e55[-1]) / e55[-1] * 100.0
        trend = max(-1.0, min(1.0, ema_diff_pct / 1.0))

        # 15m ADX
        adx_15 = adx(m15.highs(), m15.lows(), m15.closes(), 14)
        adx_val = float(adx_15[-1]) if not np.isnan(adx_15[-1]) else 0.0

        # 5m BB width percentile over last N (config: expansion.bbwidth_window)
        bbw = bollinger_width(m5.closes(), 20, 2.0)
        bbw_pct = percentile_rank(bbw, self.cfg.strategy.expansion.bbwidth_window)
        if np.isnan(bbw_pct):
            bbw_pct = 0.5

        # 5m volume regime
        vols = m5.volumes()
        vol_med = float(np.median(vols[-20:])) if len(vols) >= 20 else float(vols[-1])
        vol_ratio = m5.last_closed.volume / max(vol_med, 1e-9)

        expansion = bbw_pct < self.cfg.strategy.expansion.bbwidth_pctile
        momentum = adx_val > 22.0 and vol_ratio > 1.5
        chop = adx_val < 15.0 and bbw_pct > 0.6

        # Regime quality score in [0,1].
        # Weighted mix: trend magnitude, ADX push, non-chop.
        trend_score = min(abs(trend), 1.0)
        adx_score = min(adx_val / 40.0, 1.0)
        chop_penalty = 0.4 if chop else 0.0
        score = max(0.0, 0.5 * trend_score + 0.5 * adx_score - chop_penalty)

        return RegimeSnapshot(
            trend=trend,
            expansion=expansion,
            momentum=momentum,
            chop=chop,
            adx_15m=adx_val,
            ema_diff_1h_pct=ema_diff_pct,
            bbwidth_pctile=bbw_pct,
            session=session_name(now_ms),
            weekend=is_weekend(now_ms),
            score=score,
        )

    def pick_engine(self, regime: RegimeSnapshot) -> Optional[EngineName]:
        """Router table from DESIGN.md §E.4."""
        if regime.chop:
            return None
        # Priority: strong trend + momentum => momentum. Else strong trend => pullback.
        # Compressed base => expansion. If both compressed and trending, prefer momentum
        # unless volatility is genuinely compressed.
        candidates = []
        if regime.momentum and abs(regime.trend) >= 0.15:
            candidates.append((EngineName.MOMENTUM, 0.5 + 0.5 * abs(regime.trend)))
        if abs(regime.trend) >= 0.20 and not regime.momentum:
            candidates.append((EngineName.PULLBACK, 0.4 + 0.6 * abs(regime.trend)))
        if regime.expansion:
            candidates.append((EngineName.EXPANSION, 0.5 + 0.5 * (1 - regime.bbwidth_pctile)))

        if not candidates:
            return None
        candidates.sort(key=lambda x: -x[1])
        return candidates[0][0]
