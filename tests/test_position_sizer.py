from moha.risk.position_sizer import SymbolFilters, floor_to_step, size_position, leverage_cap_for_regime


def _filters():
    return SymbolFilters(tick_size=0.10, step_size=0.001, min_qty=0.001, min_notional=100.0)


def test_size_position_basic_risk_target():
    filt = _filters()
    equity = 10_000.0
    entry = 60_000.0
    stop = 59_400.0
    r = 0.01
    qty = size_position(equity, entry, stop, r, filt, max_effective_leverage=10.0)
    assert qty is not None
    # 100 USDT risk / 600 USDT stop distance = 0.1666... BTC, rounded to step
    assert 0.166 <= qty <= 0.167


def test_size_position_leverage_cap_binds():
    filt = _filters()
    equity = 1_000.0
    entry = 60_000.0
    stop = 59_990.0    # tiny 10-USDT stop -> would want huge notional
    r = 0.01
    qty = size_position(equity, entry, stop, r, filt, max_effective_leverage=5.0)
    assert qty is not None
    notional = qty * entry
    assert notional <= 5_001.0


def test_size_position_below_min_notional_returns_none():
    filt = _filters()
    equity = 20.0
    entry = 60_000.0
    stop = 59_000.0
    qty = size_position(equity, entry, stop, 0.01, filt, 5.0)
    assert qty is None


def test_size_position_zero_stop_returns_none():
    filt = _filters()
    qty = size_position(10_000.0, 60_000.0, 60_000.0, 0.01, filt, 5.0)
    assert qty is None


def test_floor_to_step_precision():
    assert floor_to_step(0.166999, 0.001) == 0.166


def test_leverage_ladder_picks_correct_bracket():
    class B:
        def __init__(self, m, lev): self.min = m; self.max_lev = lev
    ladder = [B(0.8, 5.0), B(0.6, 3.5), B(0.4, 2.0), B(0.0, 1.0)]
    assert leverage_cap_for_regime(0.9, ladder) == 5.0
    assert leverage_cap_for_regime(0.7, ladder) == 3.5
    assert leverage_cap_for_regime(0.5, ladder) == 2.0
    assert leverage_cap_for_regime(0.1, ladder) == 1.0
