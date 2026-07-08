"""Position + open-orders state. One BTC position at a time (§J.3)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from ..types import Trade


@dataclass
class OpenOrder:
    client_id: str
    role: str        # ENTRY|STOP|TP1|TP2|TRAIL|EMERG
    qty: float
    filled: float = 0.0
    status: str = "NEW"


@dataclass
class State:
    open_trade: Optional[Trade] = None
    open_orders: Dict[str, OpenOrder] = field(default_factory=dict)
    last_reconcile_ms: int = 0

    def has_position(self) -> bool:
        return self.open_trade is not None and self.open_trade.filled_qty > 0

    def open_trade_id(self) -> Optional[int]:
        return self.open_trade.id if self.open_trade else None
