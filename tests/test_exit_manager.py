from moha.execution.exit_manager import ExitManager
from moha.types import EngineName, ExitReason, Side, Trade


def _trade(side: Side, entry=100.0, stop=95.0, tp1=105.0, tp2=115.0):
    return Trade(
        signal_id=None, open_ts=0, side=side, engine=EngineName.MOMENTUM,
        entry_price=entry, stop_price=stop, tp1_price=tp1, tp2_price=tp2,
        qty=1.0, risk_pct=0.01, filled_qty=1.0,
    )


def test_stop_hit_long():
    em = ExitManager()
    t = _trade(Side.LONG)
    d = em.on_bar_close(t, bar_high=101, bar_low=94.0, bar_close=94.5,
                        atr_5m=1.0, bars_since_entry=1,
                        time_stop_bars=12, trail_atr_mult=1.5, entry_atr_5m=1.0)
    assert d is not None and d.reason == ExitReason.STOP


def test_stop_hit_short():
    em = ExitManager()
    t = _trade(Side.SHORT, entry=100, stop=105, tp1=95, tp2=85)
    d = em.on_bar_close(t, bar_high=106, bar_low=99, bar_close=101,
                        atr_5m=1.0, bars_since_entry=1, time_stop_bars=12,
                        trail_atr_mult=1.5, entry_atr_5m=1.0)
    assert d is not None and d.reason == ExitReason.STOP


def test_tp1_hit_moves_stop_to_breakeven():
    em = ExitManager()
    t = _trade(Side.LONG)
    d = em.on_bar_close(t, bar_high=105, bar_low=99, bar_close=104,
                        atr_5m=1.0, bars_since_entry=2, time_stop_bars=12,
                        trail_atr_mult=1.5, entry_atr_5m=1.0)
    assert d is not None and d.reason == ExitReason.TP1
    assert t.tp1_hit
    assert t.stop_price == 100.0


def test_time_stop_fires_before_tp1():
    em = ExitManager()
    t = _trade(Side.LONG)
    d = em.on_bar_close(t, bar_high=101, bar_low=99, bar_close=100.5,
                        atr_5m=1.0, bars_since_entry=12, time_stop_bars=12,
                        trail_atr_mult=1.5, entry_atr_5m=1.0)
    assert d is not None and d.reason == ExitReason.TIME


def test_vol_collapse_triggers():
    em = ExitManager()
    t = _trade(Side.LONG)
    d = em.on_bar_close(t, bar_high=100.3, bar_low=99.5, bar_close=100.0,
                        atr_5m=0.2, bars_since_entry=3, time_stop_bars=12,
                        trail_atr_mult=1.5, entry_atr_5m=1.0)
    assert d is not None and d.reason == ExitReason.VOL_COLLAPSE
