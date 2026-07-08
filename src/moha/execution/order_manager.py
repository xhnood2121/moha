"""Order manager. In LIVE this talks to Binance; in PAPER it simulates.

The public API is the same in both modes, so `main.py` doesn't branch.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Optional, Protocol

from ..types import EngineSignal, ExitReason, Side, Trade
from ..utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class Fill:
    price: float
    qty: float
    fee_usdt: float
    liquidity: str


class OrderClient(Protocol):
    async def place_market(self, symbol: str, side: Side, qty: float, reduce_only: bool, client_id: str) -> Fill: ...
    async def place_stop_market(self, symbol: str, side: Side, qty: float, stop_price: float, reduce_only: bool, client_id: str) -> str: ...
    async def cancel_all(self, symbol: str) -> None: ...


class OrderManager:
    def __init__(self, client: OrderClient, symbol: str, taker_fee_bps: float = 4.5):
        self.client = client
        self.symbol = symbol
        self.taker_fee_bps = taker_fee_bps
        self._entry_lock = asyncio.Lock()

    def _cid(self, role: str) -> str:
        return f"moha-{role}-{uuid.uuid4().hex[:16]}"

    async def enter(self, signal: EngineSignal, qty: float, risk_pct: float, now_ms: int) -> Optional[Trade]:
        async with self._entry_lock:
            try:
                fill = await self.client.place_market(
                    self.symbol, signal.side, qty, reduce_only=False, client_id=self._cid("ENTRY")
                )
            except Exception as e:  # noqa: BLE001
                log.error("enter.fail", err=str(e))
                return None

            trade = Trade(
                signal_id=None,
                open_ts=now_ms,
                side=signal.side,
                engine=signal.engine,
                entry_price=fill.price,
                stop_price=signal.stop_ref,
                tp1_price=signal.tp1_ref,
                tp2_price=signal.tp2_ref,
                qty=qty,
                risk_pct=risk_pct,
                filled_qty=fill.qty,
                fees_usdt=fill.fee_usdt,
            )
            try:
                await self.client.place_stop_market(
                    self.symbol,
                    signal.side.opposite(),
                    fill.qty,
                    signal.stop_ref,
                    reduce_only=True,
                    client_id=self._cid("STOP"),
                )
            except Exception as e:  # noqa: BLE001
                log.error("stop_place.fail", err=str(e))
                # Emergency close — we have no protective stop.
                await self._emergency_close(trade, now_ms)
                return None
            return trade

    async def exit_partial(self, trade: Trade, qty_frac: float, now_ms: int, reason: ExitReason) -> Optional[Fill]:
        qty = round(trade.filled_qty * qty_frac, 8)
        if qty <= 0:
            return None
        try:
            fill = await self.client.place_market(
                self.symbol, trade.side.opposite(), qty, reduce_only=True, client_id=self._cid(reason.value)
            )
        except Exception as e:  # noqa: BLE001
            log.error("exit_partial.fail", err=str(e), reason=reason.value)
            return None
        trade.filled_qty = max(0.0, trade.filled_qty - fill.qty)
        trade.fees_usdt += fill.fee_usdt
        if trade.filled_qty <= 0:
            trade.close_ts = now_ms
            trade.exit_reason = reason
        return fill

    async def _emergency_close(self, trade: Trade, now_ms: int) -> None:
        for attempt in range(10):
            if trade.filled_qty <= 0:
                return
            try:
                fill = await self.client.place_market(
                    self.symbol,
                    trade.side.opposite(),
                    trade.filled_qty,
                    reduce_only=True,
                    client_id=self._cid("EMERG"),
                )
                trade.filled_qty = max(0.0, trade.filled_qty - fill.qty)
                trade.fees_usdt += fill.fee_usdt
                if trade.filled_qty <= 0:
                    trade.close_ts = now_ms
                    trade.exit_reason = ExitReason.EMERG
                    return
            except Exception as e:  # noqa: BLE001
                log.error("emerg.attempt.fail", attempt=attempt, err=str(e))
                await asyncio.sleep(0.5)
        log.critical("emerg.exhausted", filled_qty=trade.filled_qty)

    async def flatten_all(self, trade: Trade, now_ms: int) -> None:
        await self.client.cancel_all(self.symbol)
        await self._emergency_close(trade, now_ms)
