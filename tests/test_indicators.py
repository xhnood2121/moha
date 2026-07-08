"""Indicator smoke tests: shape, warmup NaNs, and expected values."""
import numpy as np

from moha.indicators import atr, ema, rsi, adx, bollinger_width, percentile_rank, sma


def test_sma_matches_manual():
    v = [1, 2, 3, 4, 5, 6]
    s = sma(v, 3)
    assert np.isnan(s[0]) and np.isnan(s[1])
    assert s[2] == 2.0
    assert s[5] == 5.0


def test_ema_seed_and_shape():
    v = np.arange(100, dtype=float)
    e = ema(v, 20)
    assert e.shape == v.shape
    assert np.isnan(e[18])
    assert not np.isnan(e[19])
    assert e[-1] > e[19]  # rising trend


def test_rsi_range():
    v = np.sin(np.linspace(0, 6 * np.pi, 200)) * 10 + 100
    r = rsi(v.tolist(), 14)
    valid = r[~np.isnan(r)]
    assert (valid >= 0).all() and (valid <= 100).all()


def test_atr_positive_and_seeded():
    n = 60
    h = np.linspace(100, 110, n) + 0.5
    l = np.linspace(100, 110, n) - 0.5
    c = np.linspace(100, 110, n)
    a = atr(h.tolist(), l.tolist(), c.tolist(), 14)
    assert not np.isnan(a[-1])
    assert a[-1] > 0


def test_adx_trending_greater_than_flat():
    n = 200
    trend_c = np.linspace(100, 200, n)
    flat_c = np.full(n, 150.0) + np.random.default_rng(0).normal(0, 0.05, n)
    def hlc(c):
        h = c + 0.3
        l = c - 0.3
        return h.tolist(), l.tolist(), c.tolist()
    ta = adx(*hlc(trend_c), 14)
    fa = adx(*hlc(flat_c), 14)
    assert ta[-1] > fa[-1]


def test_bollinger_width_shape():
    c = np.random.default_rng(0).normal(100, 1, 200)
    b = bollinger_width(c.tolist(), 20, 2.0)
    assert b.shape == c.shape
    assert not np.isnan(b[-1])
    assert b[-1] > 0


def test_percentile_rank_edges():
    v = list(range(1, 101))
    pr = percentile_rank(v, 100)
    assert 0.99 <= pr <= 1.0
    pr = percentile_rank(v, 50)
    assert 0.99 <= pr <= 1.0  # last value ranks at the top of tail
