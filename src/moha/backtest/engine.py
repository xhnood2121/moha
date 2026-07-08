"""Event-driven backtest engine.

Reads 1m OHLCV candles for BTCUSDT, aggregates 5m/15m/1h internally,
runs the *same* SignalEngine + FilterStack + RiskEngine that live uses,
so behavior is identical up to fills & fees, which are modeled here.

Data format expected: a pandas DataFrame or a list of dicts with keys
`ts, open, high, low, close, volume, taker_buy_volume`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

import numpy as np

from ..config import Config
from ..data.market_data import MarketData
from ..indicators import atr
from ..risk.position_sizer import SymbolFilters, size_position, leverage_cap_for_regime
from ..risk.risk_engine import RiskEngine
from ..strategy.signal_engine import SignalEngine
from ..types import Candle, EngineSignal, ExitReason, RegimeSnapshot, Side, Trade
from .metrics import Metrics, TradeRow, compute_metrics


@dataclass
class BacktestResult:
    metrics: Metrics
    trades: List[TradeRow] = field(default_factory=list)
    equity_curve: List[tuple[int, float]] = field(default_factory=list)


def _aggregate(candles: List[Candle], factor: int) -> List[Candle]:
    """Aggregate an ordered list of 1m candles into `factor`-minute candles."""
    out: List[Candle] = []
    buf: List[Candle] = []
    for c in candles:
        buf.append(c)
        if len(buf) == factor:
            o = buf[0].open
            h = max(x.high for x in buf)
            l = min(x.low for x in buf)  # noqa: E741
            cl = buf[-1].close
            v = sum(x.volume for x in buf)
            tbv = sum(x.taker_buy_volume for x in buf)
            out.append(
                Candle(ts=buf[-1].ts, open=o, high=h, low=l, close=cl,
                       volume=v, taker_buy_volume=tbv, closed=True)
            )
            buf = []
    return out


def run_backtest(
    cfg: Config,
    candles_1m: List[Candle],
    starting_equity: float = 10_000.0,
    filters: Optional[SymbolFilters] = None,
) -> BacktestResult:
    filters = filters or SymbolFilters(tick_size=0.10, step_size=0.001, min_qty=0.001, min_notional=100.0)
    md = MarketData({
        "fast": "1m", "primary": "5m", "context_mid": "15m", "context_high": "1h",
    })
    signal_engine = SignalEngine(cfg)
    risk = RiskEngine(cfg, mode="backtest")

    equity = starting_equity
    if candles_1m:
        risk.bootstrap(equity, candles_1m[0].ts)

    trades: List[TradeRow] = []
    equity_curve: List[tuple[int, float]] = []

    open_trade: Optional[Trade] = None
    open_signal: Optional[EngineSignal] = None
    entry_atr_5m = 0.0
    bars_since_entry_5m = 0

    # Pre-aggregate 5m / 15m / 1h from 1m for efficiency.
    def aligned(ts: int, factor_min: int) -> bool:
        return (ts // 1000) % (factor_min * 60) == 0

    buf1m: List[Candle] = []
    buf5m: List[Candle] = []
    buf15m: List[Candle] = []

    for c in candles_1m:
        md.update_kline("fast", c)
        buf1m.append(c)

        # 5m rollup on aligned close.
        if len(buf1m) >= 5 and c.ts % (5 * 60_000) == 0:
            agg5 = _aggregate(buf1m[-5:], 5)[0]
            md.update_kline("primary", agg5)
            buf5m.append(agg5)
            if len(buf5m) >= 3 and agg5.ts % (15 * 60_000) == 0:
                agg15 = _aggregate(buf5m[-3:], 3)[0]  # 3 x 5m
                md.update_kline("context_mid", agg15)
                buf15m.append(agg15)
                if len(buf15m) >= 4 and agg15.ts % (60 * 60_000) == 0:
                    agg1h = _aggregate(buf15m[-4:], 4)[0]  # 4 x 15m
                    md.update_kline("context_high", agg1h)

            # -- Exit check first on 5m bar close, using intra-bar high/low --
            if open_trade is not None and open_signal is not None:
                bars_since_entry_5m += 1
                atr5_series = atr(md.primary.highs(), md.primary.lows(), md.primary.closes(), 14)
                atr_last = float(atr5_series[-1]) if not np.isnan(atr5_series[-1]) else 0.0

                exit_reason: Optional[ExitReason] = None
                exit_price = agg5.close
                sign = open_trade.side.sign
                risk_dist = abs(open_trade.entry_price - open_trade.stop_price)

                # Stop hit intrabar
                if (sign > 0 and agg5.low <= open_trade.stop_price) or (
                    sign < 0 and agg5.high >= open_trade.stop_price
                ):
                    exit_reason = ExitReason.STOP
                    exit_price = open_trade.stop_price
                elif open_trade.tp2_price and (
                    (sign > 0 and agg5.high >= open_trade.tp2_price)
                    or (sign < 0 and agg5.low <= open_trade.tp2_price)
                ):
                    exit_reason = ExitReason.TP2
                    exit_price = open_trade.tp2_price
                elif bars_since_entry_5m >= open_signal.time_stop_bars:
                    exit_reason = ExitReason.TIME
                    exit_price = agg5.close

                # TP1 partial handling: crude backtest treats as full-close-at-1R
                # when not modeled per-fraction (keeps R accounting honest).
                elif (sign > 0 and agg5.high >= open_trade.tp1_price and not open_trade.tp1_hit) or (
                    sign < 0 and agg5.low <= open_trade.tp1_price and not open_trade.tp1_hit
                ):
                    # Realize the TP1 fraction, and move stop to break-even.
                    tp1_frac = open_signal.tp1_close_frac
                    partial_pnl = sign * (open_trade.tp1_price - open_trade.entry_price) * open_trade.qty * tp1_frac
                    fee = open_trade.tp1_price * open_trade.qty * tp1_frac * (cfg.backtest.taker_fee_bps / 10000.0)
                    open_trade.pnl_usdt = (open_trade.pnl_usdt or 0.0) + partial_pnl - fee
                    open_trade.fees_usdt += fee
                    open_trade.qty *= (1 - tp1_frac)
                    open_trade.tp1_hit = True
                    open_trade.stop_price = open_trade.entry_price  # BE

                if exit_reason is not None and open_trade.qty > 0:
                    fee = exit_price * open_trade.qty * (cfg.backtest.taker_fee_bps / 10000.0)
                    pnl = sign * (exit_price - open_trade.entry_price) * open_trade.qty - fee
                    open_trade.pnl_usdt = (open_trade.pnl_usdt or 0.0) + pnl
                    open_trade.fees_usdt += fee
                    open_trade.close_ts = agg5.ts
                    open_trade.exit_reason = exit_reason
                    r_mult = (open_trade.pnl_usdt / (equity * open_trade.risk_pct)) if equity * open_trade.risk_pct > 0 else 0.0
                    open_trade.r_multiple = r_mult
                    trades.append(TradeRow(ts=agg5.ts, pnl_usdt=open_trade.pnl_usdt,
                                           r=r_mult, fees=open_trade.fees_usdt))
                    equity += open_trade.pnl_usdt
                    risk.record_trade_outcome(open_trade.pnl_usdt, equity)
                    equity_curve.append((agg5.ts, equity))
                    open_trade = None
                    open_signal = None
                    entry_atr_5m = 0.0
                    bars_since_entry_5m = 0

            # -- Signal evaluation only if flat --
            if open_trade is None:
                sig, regime, fr = signal_engine.evaluate(md, None, agg5.ts)
                if sig is not None and regime is not None and fr.ok:
                    ok, why = risk.allow_new_trade(equity, agg5.ts)
                    if ok:
                        r_pct = risk.effective_risk_pct(sig.score, regime, agg5.ts)
                        if r_pct > 0:
                            lev = leverage_cap_for_regime(regime.score, cfg.leverage.ladder)
                            qty = size_position(equity, sig.entry_ref, sig.stop_ref, r_pct, filters, lev)
                            if qty is not None:
                                # Instant fill at signal price + fee.
                                fee = sig.entry_ref * qty * (cfg.backtest.taker_fee_bps / 10000.0)
                                open_trade = Trade(
                                    signal_id=None,
                                    open_ts=agg5.ts,
                                    side=sig.side,
                                    engine=sig.engine,
                                    entry_price=sig.entry_ref,
                                    stop_price=sig.stop_ref,
                                    tp1_price=sig.tp1_ref,
                                    tp2_price=sig.tp2_ref,
                                    qty=qty,
                                    risk_pct=r_pct,
                                    filled_qty=qty,
                                    fees_usdt=fee,
                                    pnl_usdt=-fee,
                                )
                                open_signal = sig
                                atr5s = atr(md.primary.highs(), md.primary.lows(), md.primary.closes(), 14)
                                entry_atr_5m = float(atr5s[-1]) if not np.isnan(atr5s[-1]) else 0.0
                                bars_since_entry_5m = 0
                                signal_engine.filters.note_entry(sig.side, agg5.ts)

    # Final equity snapshot.
    if not equity_curve and candles_1m:
        equity_curve.append((candles_1m[-1].ts, equity))

    metrics = compute_metrics(trades, starting_equity)
    return BacktestResult(metrics=metrics, trades=trades, equity_curve=equity_curve)
