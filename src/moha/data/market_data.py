"""Rolling per-timeframe OHLCV buffers, plus book top state.

The bot only reads *closed* candles for signal generation. The current
in-progress bar is stored but flagged as `closed=False`; engines never
look at it.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional

import numpy as np

from ..types import BookTop, Candle


@dataclass
class TFBuffer:
    interval: str
    maxlen: int = 500
    candles: Deque[Candle] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.candles = deque(maxlen=self.maxlen)

    def add(self, c: Candle) -> None:
        # Replace last if it's the same open-time and unclosed → closing update.
        if self.candles and self.candles[-1].ts == c.ts:
            self.candles[-1] = c
        else:
            self.candles.append(c)

    def closed(self) -> List[Candle]:
        return [c for c in self.candles if c.closed]

    def closes(self) -> np.ndarray:
        return np.array([c.close for c in self.closed()], dtype=np.float64)

    def highs(self) -> np.ndarray:
        return np.array([c.high for c in self.closed()], dtype=np.float64)

    def lows(self) -> np.ndarray:
        return np.array([c.low for c in self.closed()], dtype=np.float64)

    def volumes(self) -> np.ndarray:
        return np.array([c.volume for c in self.closed()], dtype=np.float64)

    def taker_buy_volumes(self) -> np.ndarray:
        return np.array([c.taker_buy_volume for c in self.closed()], dtype=np.float64)

    @property
    def last_closed(self) -> Optional[Candle]:
        cs = self.closed()
        return cs[-1] if cs else None


class MarketData:
    """Owns per-timeframe buffers, current book top, and derived context."""

    def __init__(self, timeframes: Dict[str, str]):
        self.tfs = timeframes  # name -> interval string, e.g. {"primary": "5m"}
        self.buffers: Dict[str, TFBuffer] = {
            name: TFBuffer(interval=iv) for name, iv in timeframes.items()
        }
        self.book: Optional[BookTop] = None
        self.mark_price: Optional[float] = None
        self.funding_rate: Optional[float] = None       # last known
        self.next_funding_ts_ms: Optional[int] = None
        self.open_interest: Optional[float] = None
        self._oi_history: Deque[tuple[int, float]] = deque(maxlen=32)

    def update_kline(self, tf_name: str, candle: Candle) -> None:
        if tf_name in self.buffers:
            self.buffers[tf_name].add(candle)

    def update_book(self, book: BookTop) -> None:
        self.book = book

    def update_mark(self, price: float) -> None:
        self.mark_price = price

    def update_funding(self, rate: float, next_ts_ms: int) -> None:
        self.funding_rate = rate
        self.next_funding_ts_ms = next_ts_ms

    def update_open_interest(self, ts_ms: int, oi: float) -> None:
        self.open_interest = oi
        self._oi_history.append((ts_ms, oi))

    def oi_delta_pct(self, window_ms: int) -> Optional[float]:
        if not self._oi_history:
            return None
        last_ts, last_oi = self._oi_history[-1]
        threshold = last_ts - window_ms
        older = None
        for ts, oi in self._oi_history:
            if ts <= threshold:
                older = oi
        if older is None or older <= 0:
            return None
        return (last_oi - older) / older

    @property
    def primary(self) -> TFBuffer:
        return self.buffers["primary"]

    @property
    def fast(self) -> TFBuffer:
        return self.buffers["fast"]

    @property
    def context_mid(self) -> TFBuffer:
        return self.buffers["context_mid"]

    @property
    def context_high(self) -> TFBuffer:
        return self.buffers["context_high"]
