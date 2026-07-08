"""Backtest metrics — DESIGN.md §Q.3."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np


@dataclass
class TradeRow:
    ts: int
    pnl_usdt: float
    r: float
    fees: float


@dataclass
class Metrics:
    n_trades: int = 0
    total_pnl: float = 0.0
    win_rate: float = 0.0
    avg_win_r: float = 0.0
    avg_loss_r: float = 0.0
    expectancy_r: float = 0.0
    profit_factor: float = 0.0
    max_dd_pct: float = 0.0
    sharpe_daily: float = 0.0
    sortino_daily: float = 0.0
    fees_paid: float = 0.0

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def compute_metrics(trades: List[TradeRow], starting_equity: float) -> Metrics:
    m = Metrics()
    if not trades:
        return m
    m.n_trades = len(trades)
    m.total_pnl = sum(t.pnl_usdt for t in trades)
    m.fees_paid = sum(t.fees for t in trades)
    rs = np.array([t.r for t in trades])
    wins = rs[rs > 0]
    losses = rs[rs < 0]
    m.win_rate = float(len(wins) / len(rs))
    m.avg_win_r = float(wins.mean()) if len(wins) else 0.0
    m.avg_loss_r = float(losses.mean()) if len(losses) else 0.0
    m.expectancy_r = float(rs.mean())
    gross_win = float(wins.sum())
    gross_loss = float(-losses.sum())
    m.profit_factor = gross_win / gross_loss if gross_loss > 0 else float("inf")

    # Equity curve & max drawdown.
    eq = starting_equity + np.cumsum([t.pnl_usdt for t in trades])
    peak = np.maximum.accumulate(eq)
    dd = (peak - eq) / np.maximum(peak, 1e-9)
    m.max_dd_pct = float(dd.max())

    # Daily returns for Sharpe/Sortino.
    day_ms = 86_400_000
    days = {}
    for t in trades:
        d = t.ts // day_ms
        days[d] = days.get(d, 0.0) + t.pnl_usdt / starting_equity
    if days:
        daily = np.array(list(days.values()))
        if daily.std(ddof=0) > 0:
            m.sharpe_daily = float(daily.mean() / daily.std(ddof=0) * np.sqrt(365))
        neg = daily[daily < 0]
        if len(neg) and neg.std(ddof=0) > 0:
            m.sortino_daily = float(daily.mean() / neg.std(ddof=0) * np.sqrt(365))
    return m


def monte_carlo_dd(trade_pnls: List[float], starting_equity: float, iters: int = 5000, seed: int = 42) -> dict:
    if not trade_pnls:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
    rng = np.random.default_rng(seed)
    pnls = np.array(trade_pnls, dtype=np.float64)
    n = len(pnls)
    dds = np.empty(iters)
    for i in range(iters):
        shuffled = rng.permutation(pnls)
        eq = starting_equity + np.cumsum(shuffled)
        peak = np.maximum.accumulate(eq)
        dds[i] = float(((peak - eq) / np.maximum(peak, 1e-9)).max())
    return {
        "p50": float(np.quantile(dds, 0.50)),
        "p95": float(np.quantile(dds, 0.95)),
        "p99": float(np.quantile(dds, 0.99)),
        "n": n,
    }
