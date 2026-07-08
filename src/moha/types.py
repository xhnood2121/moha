"""Core dataclasses shared across the bot."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Side(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"

    @property
    def sign(self) -> int:
        return 1 if self is Side.LONG else -1

    def opposite(self) -> "Side":
        return Side.SHORT if self is Side.LONG else Side.LONG


class EngineName(str, Enum):
    MOMENTUM = "momentum"
    PULLBACK = "pullback"
    EXPANSION = "expansion"


class ExitReason(str, Enum):
    STOP = "STOP"
    TP1 = "TP1"
    TP2 = "TP2"
    TIME = "TIME"
    EMERG = "EMERG"
    OPPOSITE = "OPPOSITE"
    VOL_COLLAPSE = "VOL_COLLAPSE"
    KILL = "KILL"


@dataclass
class Candle:
    ts: int          # ms of close
    open: float
    high: float
    low: float
    close: float
    volume: float
    taker_buy_volume: float = 0.0
    closed: bool = True

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return max(self.high - self.low, 1e-12)

    @property
    def body_ratio(self) -> float:
        return self.body / self.range

    @property
    def is_bull(self) -> bool:
        return self.close > self.open

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)


@dataclass
class BookTop:
    bid: float
    bid_qty: float
    ask: float
    ask_qty: float

    @property
    def mid(self) -> float:
        return 0.5 * (self.bid + self.ask)

    @property
    def spread(self) -> float:
        return self.ask - self.bid


@dataclass
class RegimeSnapshot:
    trend: float          # -1..1
    expansion: bool
    momentum: bool
    chop: bool
    adx_15m: float
    ema_diff_1h_pct: float
    bbwidth_pctile: float
    session: str
    weekend: bool
    score: float          # 0..1 regime quality

    def as_dict(self) -> dict:
        return dict(
            trend=self.trend,
            expansion=self.expansion,
            momentum=self.momentum,
            chop=self.chop,
            adx_15m=self.adx_15m,
            ema_diff_1h_pct=self.ema_diff_1h_pct,
            bbwidth_pctile=self.bbwidth_pctile,
            session=self.session,
            weekend=self.weekend,
            score=self.score,
        )


@dataclass
class EngineSignal:
    engine: EngineName
    side: Side
    entry_ref: float
    stop_ref: float
    tp1_ref: float
    tp2_ref: Optional[float]
    score: float           # 0..1
    tp1_close_frac: float
    trail_atr_mult: float
    time_stop_bars: int
    min_rr: float
    meta: dict = field(default_factory=dict)

    @property
    def rr_tp1(self) -> float:
        risk = abs(self.entry_ref - self.stop_ref)
        return abs(self.tp1_ref - self.entry_ref) / max(risk, 1e-9)


@dataclass
class FilterResult:
    ok: bool
    reasons: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"ok": self.ok, "reasons": self.reasons}


@dataclass
class Trade:
    signal_id: Optional[int]
    open_ts: int
    side: Side
    engine: EngineName
    entry_price: float
    stop_price: float
    tp1_price: float
    tp2_price: Optional[float]
    qty: float
    risk_pct: float
    filled_qty: float = 0.0
    tp1_hit: bool = False
    close_ts: Optional[int] = None
    exit_reason: Optional[ExitReason] = None
    r_multiple: Optional[float] = None
    pnl_usdt: Optional[float] = None
    fees_usdt: float = 0.0
    funding_usdt: float = 0.0
    max_favorable: float = 0.0
    max_adverse: float = 0.0
    trail_active: bool = False
    trail_ref_price: float = 0.0
    id: Optional[int] = None
