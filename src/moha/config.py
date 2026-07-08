"""YAML + env config loader with Pydantic validation."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field, model_validator


class TimeframesCfg(BaseModel):
    fast: str = "1m"
    primary: str = "5m"
    context_mid: str = "15m"
    context_high: str = "1h"


class LeverageBracket(BaseModel):
    min: float
    max_lev: float


class LeverageCfg(BaseModel):
    effective_cap: float = 5.0
    ladder: List[LeverageBracket]


class RiskCfg(BaseModel):
    base_risk_pct: float = 0.0075
    min_risk_pct: float = 0.005
    max_risk_pct: float = 0.015
    daily_loss_cap_pct: float = 0.03
    weekly_loss_cap_pct: float = 0.07
    max_consecutive_losses: int = 4
    loss_reduce_factor: float = 0.85
    max_concurrent_positions: int = 1
    max_daily_trades: int = 8
    idle_reserve_pct: float = 0.20
    drawdown_kill_pct: float = 0.10
    first_live_days: int = 14
    first_live_capital_pct: float = 0.10
    first_live_max_risk_pct: float = 0.004

    @model_validator(mode="after")
    def _sanity(self) -> "RiskCfg":
        if self.min_risk_pct > self.base_risk_pct:
            raise ValueError("min_risk_pct > base_risk_pct")
        if self.base_risk_pct > self.max_risk_pct:
            raise ValueError("base_risk_pct > max_risk_pct")
        if not (0 < self.daily_loss_cap_pct < self.weekly_loss_cap_pct < 1):
            raise ValueError("loss caps must be 0<daily<weekly<1")
        return self


class MomentumCfg(BaseModel):
    lookback_bars: int = 20
    breakout_pct: float = 0.001
    volume_mult: float = 1.8
    min_body_ratio: float = 0.55
    min_adx_15m: float = 18
    tp1_r: float = 1.0
    tp2_r: float = 2.5
    tp1_close_frac: float = 0.5
    trail_atr_mult: float = 1.5
    time_stop_bars: int = 12
    min_rr: float = 1.8


class PullbackCfg(BaseModel):
    fib_low: float = 0.38
    fib_high: float = 0.61
    tp1_r: float = 1.0
    tp2_r: float = 2.0
    tp1_close_frac: float = 0.6
    trail_atr_mult: float = 2.0
    time_stop_bars: int = 18
    min_rr: float = 1.5


class ExpansionCfg(BaseModel):
    bbwidth_pctile: float = 0.20
    bbwidth_window: int = 40
    compressed_bars_needed: int = 6
    lookback_compressed: int = 10
    volume_mult: float = 1.5
    min_body_ratio: float = 0.6
    tp1_r: float = 1.5
    tp2_r: float = 3.0
    tp1_close_frac: float = 0.5
    trail_atr_mult: float = 2.0
    time_stop_bars: int = 24
    min_rr: float = 2.0


class StrategyCfg(BaseModel):
    momentum: MomentumCfg = MomentumCfg()
    pullback: PullbackCfg = PullbackCfg()
    expansion: ExpansionCfg = ExpansionCfg()


class SessionThresholds(BaseModel):
    high_activity_utc: List[int] = [7, 21]
    strong_hours_score: float = 0.55
    off_hours_score: float = 0.75


class FiltersCfg(BaseModel):
    spread_mult: float = 3.0
    book_depth_levels: int = 20
    book_wall_mult: float = 3.0
    news_atr_mult: float = 2.0
    round_number: float = 1000.0
    round_number_pct: float = 0.001
    session_thresholds: SessionThresholds = SessionThresholds()
    weekend_risk_scale: float = 0.5
    taker_pressure_min: float = 0.55
    funding_skip_window_min: int = 5
    funding_skip_threshold_pct: float = 0.0005
    oi_delta_pct: float = 0.05
    oi_price_pct: float = 0.002
    cooldown_bars_5m: int = 3


class ExchangeCfg(BaseModel):
    base_rest_futures: str = "https://fapi.binance.com"
    base_ws_futures: str = "wss://fstream.binance.com/ws"
    base_rest_spot: str = "https://api.binance.com"
    base_ws_spot: str = "wss://stream.binance.com/ws"
    recv_window_ms: int = 5000
    rest_max_weight_per_min: int = 2400
    orders_per_10s: int = 300
    ws_reconnect_max_delay_s: int = 30


class JournalCfg(BaseModel):
    path: str = "./data/moha.sqlite"


class AlertsCfg(BaseModel):
    telegram_enabled: bool = False
    telegram_chat_id: str = ""


class BacktestCfg(BaseModel):
    slippage_ticks: int = 1
    slippage_k_atr: float = 0.15
    taker_fee_bps: float = 4.5
    maker_fee_bps: float = 1.8
    funding_apply: bool = True


class Config(BaseModel):
    mode: str = "paper"
    symbol: str = "BTCUSDT"
    venue: str = "futures"
    margin_mode: str = "isolated"
    timeframes: TimeframesCfg = TimeframesCfg()
    risk: RiskCfg = RiskCfg()
    leverage: LeverageCfg
    strategy: StrategyCfg = StrategyCfg()
    filters: FiltersCfg = FiltersCfg()
    exchange: ExchangeCfg = ExchangeCfg()
    journal: JournalCfg = JournalCfg()
    alerts: AlertsCfg = AlertsCfg()
    backtest: BacktestCfg = BacktestCfg()

    @model_validator(mode="after")
    def _sanity(self) -> "Config":
        if self.mode not in ("backtest", "paper", "live"):
            raise ValueError(f"mode={self.mode} invalid")
        if self.venue not in ("futures", "spot"):
            raise ValueError(f"venue={self.venue} invalid")
        if self.margin_mode != "isolated":
            raise ValueError("cross margin is disabled by policy")
        return self

    def config_hash(self) -> str:
        payload = self.model_dump_json().encode()
        return hashlib.sha256(payload).hexdigest()[:16]


def load_config(path: str) -> Config:
    with open(path, "r") as f:
        raw = yaml.safe_load(f)
    return Config.model_validate(raw)


def load_secrets(env_path: Optional[str] = None) -> dict:
    if env_path and Path(env_path).exists():
        from dotenv import load_dotenv
        load_dotenv(env_path)
    return {
        "api_key": os.getenv("BINANCE_API_KEY", ""),
        "api_secret": os.getenv("BINANCE_API_SECRET", ""),
        "telegram_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
    }
