from moha.config import Config, LeverageBracket, LeverageCfg
from moha.risk.risk_engine import RiskEngine


def _cfg():
    return Config(
        mode="backtest",
        leverage=LeverageCfg(effective_cap=5.0, ladder=[
            LeverageBracket(min=0.8, max_lev=5.0),
            LeverageBracket(min=0.6, max_lev=3.5),
            LeverageBracket(min=0.4, max_lev=2.0),
            LeverageBracket(min=0.0, max_lev=1.0),
        ]),
    )


def test_daily_loss_cap_blocks():
    cfg = _cfg()
    r = RiskEngine(cfg, mode="backtest")
    now = 1_700_000_000_000
    r.bootstrap(10_000.0, now)
    # Simulate a 3.5% drop in equity within the same day.
    ok, why = r.allow_new_trade(9_650.0, now + 60_000)
    assert not ok
    assert why == "DAILY_LOSS_CAP"


def test_drawdown_kill_blocks():
    cfg = _cfg()
    r = RiskEngine(cfg, mode="backtest")
    now = 1_700_000_000_000
    r.bootstrap(10_000.0, now)
    # Advance day so the daily cap doesn't fire first.
    day2 = now + 3 * 86_400_000
    r.state.day_start_equity = 9_000.0
    r.state.week_start_equity = 9_500.0
    ok, why = r.allow_new_trade(8_900.0, day2)
    assert not ok
    assert why == "DRAWDOWN_KILL"


def test_max_daily_trades_blocks():
    cfg = _cfg()
    r = RiskEngine(cfg, mode="backtest")
    now = 1_700_000_000_000
    r.bootstrap(10_000.0, now)
    r.state.trades_today = cfg.risk.max_daily_trades
    ok, why = r.allow_new_trade(10_000.0, now)
    assert not ok
    assert why == "MAX_DAILY_TRADES"


def test_consecutive_losses_reduce_risk():
    cfg = _cfg()
    r = RiskEngine(cfg, mode="backtest")
    now = 1_700_000_000_000
    r.bootstrap(10_000.0, now)
    initial = r.state.effective_risk_pct
    r.record_trade_outcome(-100.0, 9_900.0)
    r.record_trade_outcome(-100.0, 9_800.0)
    assert r.state.effective_risk_pct < initial
    assert r.state.consecutive_losses == 2


def test_win_resets_streak():
    cfg = _cfg()
    r = RiskEngine(cfg, mode="backtest")
    now = 1_700_000_000_000
    r.bootstrap(10_000.0, now)
    r.record_trade_outcome(-100.0, 9_900.0)
    r.record_trade_outcome(200.0, 10_100.0)
    assert r.state.consecutive_losses == 0
    assert r.state.consecutive_wins == 1
