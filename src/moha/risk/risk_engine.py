"""Risk engine — DESIGN.md §J.

Owns caps: per-trade risk %, daily/weekly loss caps, drawdown from
all-time-high kill, cooldown after losing streak, max daily trades.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ..config import Config
from ..types import RegimeSnapshot
from ..utils.time_utils import is_weekend, ms_to_dt


@dataclass
class RiskState:
    equity_high_watermark: float = 0.0
    session_start_equity: float = 0.0
    day_start_equity: float = 0.0
    week_start_equity: float = 0.0
    day_key: str = ""            # YYYY-MM-DD UTC
    week_key: str = ""           # YYYY-Www ISO week
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    trades_today: int = 0
    effective_risk_pct: float = 0.0
    live_start_ts_ms: int = 0
    events: list = field(default_factory=list)


class RiskEngine:
    def __init__(self, cfg: Config, mode: str):
        self.cfg = cfg
        self.mode = mode
        self.state = RiskState()

    def bootstrap(self, equity: float, now_ms: int) -> None:
        self.state.equity_high_watermark = equity
        self.state.session_start_equity = equity
        self.state.day_start_equity = equity
        self.state.week_start_equity = equity
        self.state.day_key, self.state.week_key = self._keys(now_ms)
        self.state.effective_risk_pct = self.cfg.risk.base_risk_pct
        if self.mode == "live":
            self.state.live_start_ts_ms = now_ms

    def _keys(self, now_ms: int) -> tuple[str, str]:
        dt = ms_to_dt(now_ms)
        return dt.strftime("%Y-%m-%d"), dt.strftime("%G-W%V")

    def maybe_roll_day(self, equity: float, now_ms: int) -> None:
        dk, wk = self._keys(now_ms)
        if dk != self.state.day_key:
            self.state.day_key = dk
            self.state.day_start_equity = equity
            self.state.trades_today = 0
        if wk != self.state.week_key:
            self.state.week_key = wk
            self.state.week_start_equity = equity

    # ----- pre-trade gate -----

    def allow_new_trade(self, equity: float, now_ms: int) -> tuple[bool, str]:
        self.maybe_roll_day(equity, now_ms)
        r = self.cfg.risk

        if equity <= 0:
            return False, "EQUITY_NON_POSITIVE"

        day_dd = (self.state.day_start_equity - equity) / max(self.state.day_start_equity, 1e-9)
        if day_dd >= r.daily_loss_cap_pct:
            return False, "DAILY_LOSS_CAP"

        week_dd = (self.state.week_start_equity - equity) / max(self.state.week_start_equity, 1e-9)
        if week_dd >= r.weekly_loss_cap_pct:
            return False, "WEEKLY_LOSS_CAP"

        peak = max(self.state.equity_high_watermark, equity)
        self.state.equity_high_watermark = peak
        dd_ath = (peak - equity) / max(peak, 1e-9)
        if dd_ath >= r.drawdown_kill_pct:
            return False, "DRAWDOWN_KILL"

        if self.state.consecutive_losses >= r.max_consecutive_losses:
            return False, "LOSS_STREAK"

        if self.state.trades_today >= r.max_daily_trades:
            return False, "MAX_DAILY_TRADES"

        return True, "OK"

    # ----- sizing modifiers -----

    def effective_risk_pct(
        self,
        signal_score: float,
        regime: RegimeSnapshot,
        now_ms: int,
    ) -> float:
        r = self.cfg.risk
        # Ladder based on signal quality (see DESIGN.md §J.1).
        if signal_score >= 0.85 and regime.score >= 0.75:
            base = min(r.max_risk_pct, max(r.base_risk_pct * 1.5, 0.0125))
        elif signal_score >= 0.65:
            base = min(r.base_risk_pct * 1.2, r.max_risk_pct)
        elif signal_score >= 0.55:
            base = r.min_risk_pct
        else:
            return 0.0

        # Reduce after losses (Kelly-fractional).
        # `effective_risk_pct` in state tracks the decayed baseline.
        base = min(base, self.state.effective_risk_pct * (base / r.base_risk_pct))
        base = max(base, r.min_risk_pct)

        # Weekend / off-hours haircut.
        if is_weekend(now_ms):
            base *= self.cfg.filters.weekend_risk_scale

        # Live pilot cap for first N days.
        if self.mode == "live" and self.state.live_start_ts_ms:
            days_live = (now_ms - self.state.live_start_ts_ms) / 86_400_000.0
            if days_live < r.first_live_days:
                base = min(base, r.first_live_max_risk_pct)

        return max(r.min_risk_pct, min(base, r.max_risk_pct))

    # ----- outcomes -----

    def record_trade_outcome(self, pnl_usdt: float, equity_after: float) -> None:
        r = self.cfg.risk
        self.state.trades_today += 1
        if pnl_usdt < 0:
            self.state.consecutive_losses += 1
            self.state.consecutive_wins = 0
            new_rp = max(self.state.effective_risk_pct * r.loss_reduce_factor, r.min_risk_pct)
            self.state.effective_risk_pct = new_rp
        elif pnl_usdt > 0:
            self.state.consecutive_wins += 1
            self.state.consecutive_losses = 0
            # Slow re-normalization toward base.
            drift = (r.base_risk_pct - self.state.effective_risk_pct) * 0.5
            self.state.effective_risk_pct = min(
                r.base_risk_pct, self.state.effective_risk_pct + drift
            )
        self.state.equity_high_watermark = max(self.state.equity_high_watermark, equity_after)
