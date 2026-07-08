"""Paper trading OrderClient. Simulates fills off `bookTicker` mid.

Slippage: `spread/2 + k * atr%` on market orders. Stops fill at
stop price with a fixed tick of adverse slip.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from ..types import Side
from .order_manager import Fill


@dataclass
class PaperConfig:
    taker_fee_bps: float = 4.5
    slippage_ticks: int = 1
    slippage_k_atr: float = 0.15
    tick_size: float = 0.10


class PaperClient:
    def __init__(
        self,
        get_mid: Callable[[], float],
        get_atr_pct: Callable[[], float],
        cfg: PaperConfig,
    ):
        self.get_mid = get_mid
        self.get_atr_pct = get_atr_pct
        self.cfg = cfg
        self.resting_stops: dict[str, dict] = {}

    async def place_market(self, symbol: str, side: Side, qty: float, reduce_only: bool, client_id: str) -> Fill:
        mid = self.get_mid()
        atr_pct = max(self.get_atr_pct(), 0.0)
        slippage = (self.cfg.slippage_ticks * self.cfg.tick_size / max(mid, 1e-9)
                    + self.cfg.slippage_k_atr * atr_pct)
        # Long buys pay the offer side + slippage; short sells hit bid − slippage.
        adj = 1 + slippage if side is Side.LONG else 1 - slippage
        price = mid * adj
        fee = price * qty * (self.cfg.taker_fee_bps / 10000.0)
        return Fill(price=price, qty=qty, fee_usdt=fee, liquidity="TAKER")

    async def place_stop_market(
        self, symbol: str, side: Side, qty: float, stop_price: float, reduce_only: bool, client_id: str
    ) -> str:
        # Store; the backtest / paper harness will call `trigger_stops`.
        self.resting_stops[client_id] = dict(symbol=symbol, side=side, qty=qty, stop=stop_price)
        return client_id

    async def cancel_all(self, symbol: str) -> None:
        self.resting_stops.clear()

    def trigger_stops(self, high: float, low: float) -> Optional[Fill]:
        """Called by the paper/backtest loop on each 1m bar to check stops.

        Returns a Fill if a stop was triggered.
        """
        fill: Optional[Fill] = None
        for cid, s in list(self.resting_stops.items()):
            hit = (s["side"] is Side.SHORT and low <= s["stop"]) or (
                s["side"] is Side.LONG and high >= s["stop"]
            )
            if hit:
                slip_ticks = self.cfg.slippage_ticks * self.cfg.tick_size
                # Adverse fill from a stop-market.
                px = s["stop"] - slip_ticks if s["side"] is Side.SHORT else s["stop"] + slip_ticks
                fee = px * s["qty"] * (self.cfg.taker_fee_bps / 10000.0)
                fill = Fill(price=px, qty=s["qty"], fee_usdt=fee, liquidity="TAKER")
                self.resting_stops.pop(cid, None)
                break
        return fill
