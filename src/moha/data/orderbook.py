"""Top-N depth snapshot used only for microstructure filters (F.1, F.2)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from ..types import BookTop


@dataclass
class DepthSnapshot:
    bids: List[Tuple[float, float]]   # [(price, qty), ...] sorted desc by price
    asks: List[Tuple[float, float]]   # sorted asc by price

    def top(self) -> BookTop:
        if not self.bids or not self.asks:
            return BookTop(bid=0.0, bid_qty=0.0, ask=0.0, ask_qty=0.0)
        b_p, b_q = self.bids[0]
        a_p, a_q = self.asks[0]
        return BookTop(bid=b_p, bid_qty=b_q, ask=a_p, ask_qty=a_q)

    def near_bid_size(self, levels: int) -> float:
        return sum(q for _, q in self.bids[:levels])

    def near_ask_size(self, levels: int) -> float:
        return sum(q for _, q in self.asks[:levels])
