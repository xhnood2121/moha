"""Live and paper runtime loops.

Wires the WebSocket, market data, signal engine, risk, order manager,
and journal into a single supervised asyncio program.
"""
from __future__ import annotations

import asyncio
import time
from typing import Optional

from .config import Config
from .data.market_data import MarketData
from .exchange.binance_rest import BinanceFuturesREST, Credentials
from .exchange.binance_ws import BinanceMarketWS, WSEvent
from .exchange.rate_limiter import BinanceLimiters
from .execution.order_manager import OrderManager
from .execution.paper_client import PaperClient, PaperConfig
from .execution.state_manager import State
from .indicators import atr
from .risk.kill_switch import KillSwitch
from .risk.position_sizer import SymbolFilters, size_position, leverage_cap_for_regime
from .risk.risk_engine import RiskEngine
from .storage.journal import Journal
from .strategy.signal_engine import SignalEngine
from .types import Candle, ExitReason, RegimeSnapshot
from .utils.alerts import Alerts
from .utils.logger import get_logger

log = get_logger("moha.runtime")


class _StopSignal(Exception):
    """Raised by the supervisor to break the loop cleanly."""


class Supervisor:
    def __init__(
        self,
        cfg: Config,
        rest: Optional[BinanceFuturesREST],
        journal: Journal,
        alerts: Alerts,
        starting_equity: float,
    ):
        self.cfg = cfg
        self.rest = rest
        self.journal = journal
        self.alerts = alerts
        self.md = MarketData({
            "fast": cfg.timeframes.fast,
            "primary": cfg.timeframes.primary,
            "context_mid": cfg.timeframes.context_mid,
            "context_high": cfg.timeframes.context_high,
        })
        self.signal_engine = SignalEngine(cfg)
        self.risk = RiskEngine(cfg, mode=cfg.mode)
        self.kill = KillSwitch()
        self.state = State()
        self.equity = starting_equity
        self._last_5m_ts = 0
        self._entry_atr_5m = 0.0
        self._bars_since_entry_5m = 0
        self._symbol_filters = SymbolFilters(
            tick_size=0.10, step_size=0.001, min_qty=0.001, min_notional=100.0
        )
        self.order_manager: Optional[OrderManager] = None
        self.paper_client: Optional[PaperClient] = None

    async def bootstrap(self) -> None:
        await self.journal.open()
        self.risk.bootstrap(self.equity, int(time.time() * 1000))
        if self.rest is not None:
            await self.rest.start()
            await self.rest.verify_key_safety()
            info = await self.rest.exchange_info()
            for s in info.get("symbols", []):
                if s.get("symbol") == self.cfg.symbol:
                    for f in s.get("filters", []):
                        if f.get("filterType") == "PRICE_FILTER":
                            self._symbol_filters.tick_size = float(f["tickSize"])
                        elif f.get("filterType") == "LOT_SIZE":
                            self._symbol_filters.step_size = float(f["stepSize"])
                            self._symbol_filters.min_qty = float(f["minQty"])
                        elif f.get("filterType") == "MIN_NOTIONAL":
                            self._symbol_filters.min_notional = float(f["notional"])
                    break
            # Warm-up klines
            for tf_name in ("fast", "primary", "context_mid", "context_high"):
                iv = getattr(self.cfg.timeframes, tf_name)
                data = await self.rest.klines(self.cfg.symbol, iv, limit=500)
                for k in data:
                    self.md.update_kline(
                        tf_name,
                        Candle(
                            ts=int(k[0]),
                            open=float(k[1]), high=float(k[2]), low=float(k[3]),
                            close=float(k[4]), volume=float(k[5]),
                            taker_buy_volume=float(k[9]) if len(k) > 9 else 0.0,
                            closed=True,
                        ),
                    )

    async def on_ws_event(self, ev: WSEvent) -> None:
        if ev.kind == "kline":
            # Map interval string back to timeframe name.
            tf_name = _tf_name_for(self.cfg, ev.tf or "")
            if tf_name is None:
                return
            self.md.update_kline(tf_name, ev.payload)  # type: ignore[arg-type]
            if tf_name == "primary" and ev.payload.closed:  # type: ignore[union-attr]
                await self.on_primary_bar_close(ev.payload.ts)  # type: ignore[union-attr]
        elif ev.kind == "book":
            self.md.update_book(ev.payload)  # type: ignore[arg-type]
            self.signal_engine.filters.record_spread(ev.payload.spread)  # type: ignore[union-attr]
        elif ev.kind == "mark":
            mark, funding, next_ts = ev.payload  # type: ignore[misc]
            self.md.update_mark(float(mark))
            self.md.update_funding(float(funding), int(next_ts))

    async def on_primary_bar_close(self, ts_ms: int) -> None:
        if ts_ms == self._last_5m_ts:
            return
        self._last_5m_ts = ts_ms
        await self._check_exit_paths(ts_ms)
        await self._maybe_enter(ts_ms)

    async def _maybe_enter(self, ts_ms: int) -> None:
        if self.state.has_position() or self.kill.tripped:
            return
        sig, regime, fr = self.signal_engine.evaluate(self.md, None, ts_ms)
        if sig is None or regime is None:
            return
        sid = await self.journal.log_signal(
            ts_ms, sig.engine, sig.side, sig.entry_ref, sig.stop_ref,
            sig.tp1_ref, sig.tp2_ref, sig.score, regime, fr.reasons, fr.ok,
        )
        if not fr.ok:
            return
        ok, why = self.risk.allow_new_trade(self.equity, ts_ms)
        if not ok:
            await self.journal.log_event(ts_ms, "INFO", "RISK", f"gate.blocked:{why}")
            return
        r_pct = self.risk.effective_risk_pct(sig.score, regime, ts_ms)
        if r_pct <= 0:
            return
        lev = leverage_cap_for_regime(regime.score, self.cfg.leverage.ladder)
        qty = size_position(self.equity, sig.entry_ref, sig.stop_ref, r_pct, self._symbol_filters, lev)
        if qty is None:
            return
        if self.order_manager is None:
            return
        trade = await self.order_manager.enter(sig, qty, r_pct, ts_ms)
        if trade is None:
            await self.alerts.page("ENTER_FAIL", f"{sig.engine.value} {sig.side.value}")
            return
        trade.signal_id = sid
        tid = await self.journal.log_trade(trade, sid)
        self.state.open_trade = trade
        self.signal_engine.filters.note_entry(sig.side, ts_ms)
        # Cache entry ATR for volatility-collapse exits.
        highs = self.md.primary.highs()
        lows = self.md.primary.lows()
        closes = self.md.primary.closes()
        atr5 = atr(highs, lows, closes, 14)
        self._entry_atr_5m = float(atr5[-1]) if len(atr5) and not (atr5[-1] != atr5[-1]) else 0.0
        self._bars_since_entry_5m = 0
        await self.journal.log_event(ts_ms, "INFO", "TRADE", f"open:{sig.engine.value}:{sig.side.value}",
                                     {"qty": qty, "score": sig.score, "regime_score": regime.score, "trade_id": tid})

    async def _check_exit_paths(self, ts_ms: int) -> None:
        if not self.state.has_position():
            return
        trade = self.state.open_trade
        assert trade is not None
        m5 = self.md.primary
        if not m5.last_closed:
            return
        bar = m5.last_closed
        highs = m5.highs()
        lows = m5.lows()
        closes = m5.closes()
        atr5 = atr(highs, lows, closes, 14)
        atr_last = float(atr5[-1]) if len(atr5) and atr5[-1] == atr5[-1] else 0.0
        self._bars_since_entry_5m += 1

        from .execution.exit_manager import ExitManager
        em = ExitManager()
        decision = em.on_bar_close(
            trade=trade,
            bar_high=bar.high,
            bar_low=bar.low,
            bar_close=bar.close,
            atr_5m=atr_last,
            bars_since_entry=self._bars_since_entry_5m,
            time_stop_bars=self._time_stop_bars(),
            trail_atr_mult=self._trail_atr_mult(),
            entry_atr_5m=self._entry_atr_5m,
        )
        if decision is None:
            return
        if self.order_manager is None:
            return
        fill = await self.order_manager.exit_partial(trade, decision.qty_frac, ts_ms, decision.reason)
        if fill is None:
            await self.alerts.page("EXIT_FAIL", decision.reason.value)
            return
        # Realize P&L for the closed slice.
        sign = trade.side.sign
        realized = sign * (fill.price - trade.entry_price) * fill.qty - fill.fee_usdt
        self.equity += realized
        if trade.filled_qty <= 0:
            trade.pnl_usdt = (trade.pnl_usdt or 0.0) + realized
            trade.r_multiple = (trade.pnl_usdt or 0.0) / (self.equity * trade.risk_pct) if self.equity * trade.risk_pct > 0 else 0.0
            await self.journal.log_trade(trade, trade.signal_id)
            self.risk.record_trade_outcome(trade.pnl_usdt or 0.0, self.equity)
            self.state.open_trade = None
        await self.journal.log_event(ts_ms, "INFO", "EXIT", decision.reason.value,
                                     {"price": fill.price, "qty": fill.qty})

    def _time_stop_bars(self) -> int:
        # Pick a defensive maximum across engines; each engine's signal
        # stored its own but state doesn't retain it here.
        return max(
            self.cfg.strategy.momentum.time_stop_bars,
            self.cfg.strategy.pullback.time_stop_bars,
            self.cfg.strategy.expansion.time_stop_bars,
        )

    def _trail_atr_mult(self) -> float:
        return self.cfg.strategy.pullback.trail_atr_mult


def _tf_name_for(cfg: Config, interval: str) -> Optional[str]:
    for name in ("fast", "primary", "context_mid", "context_high"):
        if getattr(cfg.timeframes, name) == interval:
            return name
    return None


# ---------------- entry points ----------------

async def run_paper(cfg: Config, secrets: dict, starting_equity: float) -> None:
    """Paper trading: live WebSocket, simulated fills, no keys required."""
    limiters = BinanceLimiters(cfg.exchange.rest_max_weight_per_min, cfg.exchange.orders_per_10s)
    rest = None
    if secrets.get("api_key") and secrets.get("api_secret"):
        rest = BinanceFuturesREST(
            cfg.exchange.base_rest_futures,
            Credentials(secrets["api_key"], secrets["api_secret"]),
            limiters, cfg.exchange.recv_window_ms,
        )
    journal = Journal(cfg.journal.path)
    alerts = Alerts(cfg.alerts.telegram_enabled, secrets.get("telegram_token"), cfg.alerts.telegram_chat_id)
    sup = Supervisor(cfg, rest, journal, alerts, starting_equity)
    await sup.bootstrap()

    paper_cfg = PaperConfig(
        taker_fee_bps=cfg.backtest.taker_fee_bps,
        slippage_ticks=cfg.backtest.slippage_ticks,
        slippage_k_atr=cfg.backtest.slippage_k_atr,
        tick_size=sup._symbol_filters.tick_size,
    )

    def get_mid() -> float:
        if sup.md.book:
            return sup.md.book.mid
        if sup.md.mark_price:
            return sup.md.mark_price
        return 0.0

    def get_atr_pct() -> float:
        highs = sup.md.primary.highs()
        lows = sup.md.primary.lows()
        closes = sup.md.primary.closes()
        a = atr(highs, lows, closes, 14)
        if len(a) == 0 or a[-1] != a[-1] or closes[-1] == 0:
            return 0.0
        return float(a[-1] / closes[-1])

    paper = PaperClient(get_mid, get_atr_pct, paper_cfg)
    sup.paper_client = paper
    sup.order_manager = OrderManager(paper, cfg.symbol, cfg.backtest.taker_fee_bps)

    ws = BinanceMarketWS(
        cfg.exchange.base_ws_futures, cfg.symbol,
        [cfg.timeframes.fast, cfg.timeframes.primary, cfg.timeframes.context_mid, cfg.timeframes.context_high],
        sup.on_ws_event,
        cfg.exchange.ws_reconnect_max_delay_s,
    )
    ws_task = asyncio.create_task(ws.run())
    log.info("paper.running")
    try:
        await ws_task
    finally:
        if rest is not None:
            await rest.close()
        await journal.close()


async def run_live(cfg: Config, secrets: dict) -> None:
    """Live trading. Requires keys. Enforces safety checks in bootstrap()."""
    limiters = BinanceLimiters(cfg.exchange.rest_max_weight_per_min, cfg.exchange.orders_per_10s)
    rest = BinanceFuturesREST(
        cfg.exchange.base_rest_futures,
        Credentials(secrets["api_key"], secrets["api_secret"]),
        limiters, cfg.exchange.recv_window_ms,
    )
    journal = Journal(cfg.journal.path)
    alerts = Alerts(cfg.alerts.telegram_enabled, secrets.get("telegram_token"), cfg.alerts.telegram_chat_id)
    sup = Supervisor(cfg, rest, journal, alerts, starting_equity=0.0)
    await sup.bootstrap()
    # Read wallet balance.
    info = await rest.account_info()
    equity = float(info.get("totalWalletBalance", 0.0))
    sup.equity = equity
    sup.risk.bootstrap(equity, int(time.time() * 1000))

    from .execution.order_manager import OrderManager

    class LiveClient:
        """Adapter from OrderClient protocol to BinanceFuturesREST."""

        def __init__(self, r: BinanceFuturesREST):
            self.r = r

        async def place_market(self, symbol, side, qty, reduce_only, client_id):
            resp = await self.r.new_order(
                symbol=symbol, side=side, order_type="MARKET", qty=qty,
                reduce_only=reduce_only, client_order_id=client_id,
            )
            price = float(resp.get("avgPrice") or resp.get("price") or 0.0)
            fee = price * qty * (cfg.backtest.taker_fee_bps / 10000.0)
            from .execution.order_manager import Fill
            return Fill(price=price, qty=float(resp.get("executedQty", qty)), fee_usdt=fee, liquidity="TAKER")

        async def place_stop_market(self, symbol, side, qty, stop_price, reduce_only, client_id):
            resp = await self.r.new_order(
                symbol=symbol, side=side, order_type="STOP_MARKET", qty=qty,
                stop_price=stop_price, reduce_only=reduce_only, client_order_id=client_id,
            )
            return str(resp.get("orderId"))

        async def cancel_all(self, symbol):
            await self.r.cancel_all_open(symbol)

    sup.order_manager = OrderManager(LiveClient(rest), cfg.symbol, cfg.backtest.taker_fee_bps)

    ws = BinanceMarketWS(
        cfg.exchange.base_ws_futures, cfg.symbol,
        [cfg.timeframes.fast, cfg.timeframes.primary, cfg.timeframes.context_mid, cfg.timeframes.context_high],
        sup.on_ws_event,
        cfg.exchange.ws_reconnect_max_delay_s,
    )
    ws_task = asyncio.create_task(ws.run())
    log.info("live.running", equity=equity)
    try:
        await ws_task
    finally:
        await rest.close()
        await journal.close()
