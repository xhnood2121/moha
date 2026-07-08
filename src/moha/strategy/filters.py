"""Binance-specific pre-trade filters — DESIGN.md §F.1 through §F.10."""
from __future__ import annotations

from typing import Optional

import numpy as np

from ..config import Config
from ..data.market_data import MarketData
from ..data.orderbook import DepthSnapshot
from ..indicators import atr
from ..types import EngineSignal, FilterResult, Side
from ..utils.time_utils import is_weekend, utc_hour


class FilterStack:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.f = cfg.filters
        self._spread_hist: list[float] = []
        self._last_entry_ts: dict[Side, int] = {}

    # ----- persistent state -----

    def note_entry(self, side: Side, ts_ms: int) -> None:
        self._last_entry_ts[side] = ts_ms

    def record_spread(self, spread: float) -> None:
        self._spread_hist.append(spread)
        if len(self._spread_hist) > 720:  # ~1h of 5s samples
            self._spread_hist = self._spread_hist[-720:]

    # ----- checks -----

    def check(
        self,
        signal: EngineSignal,
        md: MarketData,
        depth: Optional[DepthSnapshot],
        now_ms: int,
    ) -> FilterResult:
        reasons: list[str] = []

        # F.1 spread filter
        if md.book is not None and self._spread_hist:
            median_spread = float(np.median(self._spread_hist[-360:])) if self._spread_hist else 0.0
            if median_spread > 0 and md.book.spread > self.f.spread_mult * median_spread:
                reasons.append("F1_SPREAD")

        # F.2 liquidity wall
        if depth is not None:
            bid = depth.near_bid_size(self.f.book_depth_levels)
            ask = depth.near_ask_size(self.f.book_depth_levels)
            if signal.side is Side.LONG and ask > self.f.book_wall_mult * bid > 0:
                reasons.append("F2_ASK_WALL")
            if signal.side is Side.SHORT and bid > self.f.book_wall_mult * ask > 0:
                reasons.append("F2_BID_WALL")

        # F.3 volatility filter — 1m ATR spike vs 24h median
        m1 = md.fast
        if len(m1.closes()) >= 60:
            atr1 = atr(m1.highs(), m1.lows(), m1.closes(), 14)
            if not np.isnan(atr1[-1]):
                lookback = min(len(atr1), 60 * 24)
                med = float(np.nanmedian(atr1[-lookback:]))
                if med > 0 and atr1[-1] > self.f.news_atr_mult * med:
                    reasons.append("F3_NEWS_ATR")

        # F.4 round-number proximity
        rn = self.f.round_number
        near_round = abs((signal.entry_ref % rn) - rn / 2) > (rn / 2) * (1 - self.f.round_number_pct)
        # More useful: distance from nearest multiple as fraction of price:
        nearest = round(signal.entry_ref / rn) * rn
        if abs(signal.entry_ref - nearest) / signal.entry_ref < self.f.round_number_pct:
            # Only reject if the round was rejected in the last 3 hourly touches
            # (approximation: last 3 hours of 5m bars saw closes reversing across it).
            m5 = md.primary
            closes = m5.closes()
            if len(closes) >= 36:
                touches = 0
                for i in range(-36, -1):
                    if (closes[i - 1] - nearest) * (closes[i + 1] - nearest) < 0:
                        touches += 1
                if touches >= 3:
                    reasons.append("F4_ROUND_REJECTED")
        _ = near_round

        # F.5 session filter (hard: below score threshold)
        h = utc_hour(now_ms)
        start, end = self.f.session_thresholds.high_activity_utc
        if start <= h < end:
            min_score = self.f.session_thresholds.strong_hours_score
        else:
            min_score = self.f.session_thresholds.off_hours_score
        if signal.score < min_score:
            reasons.append(f"F5_SCORE_LT_{min_score:.2f}")

        # F.6 abnormal candle
        m5 = md.primary
        if m5.last_closed and len(m5.closes()) >= 20:
            atr5 = atr(m5.highs(), m5.lows(), m5.closes(), 14)
            if not np.isnan(atr5[-1]) and atr5[-1] > 0:
                if m5.last_closed.range > 3.0 * float(atr5[-1]):
                    reasons.append("F6_ABNORMAL_CANDLE")

        # F.7 taker pressure
        if m5.last_closed and m5.last_closed.volume > 0:
            tb = m5.last_closed.taker_buy_volume
            ratio = tb / m5.last_closed.volume
            if signal.side is Side.LONG and ratio < self.f.taker_pressure_min:
                reasons.append("F7_TAKER_LONG")
            if signal.side is Side.SHORT and (1 - ratio) < self.f.taker_pressure_min:
                reasons.append("F7_TAKER_SHORT")

        # F.8 funding filter
        if md.funding_rate is not None and md.next_funding_ts_ms is not None:
            mins_to_funding = (md.next_funding_ts_ms - now_ms) / 60000.0
            if 0 <= mins_to_funding <= self.f.funding_skip_window_min:
                signed = md.funding_rate * signal.side.sign
                if signed < -self.f.funding_skip_threshold_pct:
                    reasons.append("F8_FUNDING")

        # F.9 open interest filter
        oi_d = md.oi_delta_pct(30 * 60 * 1000)
        if oi_d is not None and m5.last_closed is not None:
            closes = m5.closes()
            if len(closes) >= 6:
                p_change = (closes[-1] - closes[-6]) / closes[-6]
                if signal.side is Side.LONG and oi_d > self.f.oi_delta_pct and p_change < self.f.oi_price_pct:
                    reasons.append("F9_OI_LONG_LATE")
                if signal.side is Side.SHORT and oi_d > self.f.oi_delta_pct and -p_change < self.f.oi_price_pct:
                    reasons.append("F9_OI_SHORT_LATE")

        # F.10 cooldown
        last = self._last_entry_ts.get(signal.side)
        if last is not None:
            elapsed_bars = (now_ms - last) / (5 * 60 * 1000)
            if elapsed_bars < self.f.cooldown_bars_5m:
                reasons.append("F10_COOLDOWN")

        return FilterResult(ok=not reasons, reasons=reasons)
