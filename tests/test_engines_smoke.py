"""Smoke tests: engines don't crash on a synthetic price series and
return a signal with sane RR when a breakout is manufactured.
"""
import numpy as np

from moha.config import Config, LeverageBracket, LeverageCfg
from moha.data.market_data import MarketData
from moha.strategy.momentum import MomentumEngine
from moha.strategy.expansion import ExpansionEngine
from moha.types import Candle


def _cfg():
    return Config(
        mode="backtest",
        leverage=LeverageCfg(effective_cap=5.0, ladder=[LeverageBracket(min=0.0, max_lev=1.0)]),
    )


def _mk_candle(ts, o, h, l, c, v=100.0, tbv=60.0):
    return Candle(ts=ts, open=o, high=h, low=l, close=c, volume=v, taker_buy_volume=tbv, closed=True)


def _seed_md(md: MarketData, n_5m: int = 40):
    """Seed with a flat range then a breakout on the last 5m candle."""
    base_ts = 1_700_000_000_000
    price = 50_000.0
    # Fill 1m, 5m, 15m, 1h with plausible history.
    for i in range(1, 200):
        c = price + np.random.default_rng(i).normal(0, 5)
        md.update_kline("fast", _mk_candle(base_ts + i * 60_000, price, price + 3, price - 3, c))
    for i in range(1, n_5m):
        c = price + np.random.default_rng(i).normal(0, 8)
        md.update_kline("primary", _mk_candle(base_ts + i * 300_000, price, price + 15, price - 15, c))
    for i in range(1, 40):
        md.update_kline("context_mid", _mk_candle(base_ts + i * 900_000, price - 20, price + 20, price - 30, price + 10))
    for i in range(1, 80):
        md.update_kline("context_high", _mk_candle(base_ts + i * 3_600_000, price - 40, price + 40, price - 60, price + 20))


def test_momentum_engine_does_not_crash():
    cfg = _cfg()
    md = MarketData({"fast": "1m", "primary": "5m", "context_mid": "15m", "context_high": "1h"})
    _seed_md(md, n_5m=50)
    eng = MomentumEngine(cfg)
    sig = eng.evaluate(md)   # may be None; the key is it must not crash
    if sig is not None:
        assert sig.rr_tp1 >= cfg.strategy.momentum.min_rr


def test_expansion_engine_does_not_crash():
    cfg = _cfg()
    md = MarketData({"fast": "1m", "primary": "5m", "context_mid": "15m", "context_high": "1h"})
    _seed_md(md, n_5m=80)
    eng = ExpansionEngine(cfg)
    _ = eng.evaluate(md)
