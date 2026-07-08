"""Hard kill-switch — DESIGN.md §J.7 + §T."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class KillSwitch:
    tripped: bool = False
    reason: Optional[str] = None
    history: list = field(default_factory=list)

    def trip(self, reason: str) -> None:
        if not self.tripped:
            self.tripped = True
            self.reason = reason
            self.history.append(reason)

    def reset(self) -> None:
        """Requires human action; do not call in normal loops."""
        self.tripped = False
        self.reason = None

    def check_ws_gap(self, ws_gap_sec: float, position_open: bool) -> None:
        if position_open and ws_gap_sec > 10:
            self.trip("WS_GAP_WITH_POSITION")

    def check_rest_error_rate(self, error_rate: float, position_open: bool) -> None:
        if position_open and error_rate > 0.10:
            self.trip("REST_ERROR_RATE")

    def check_slippage(self, slippage_pct: float) -> None:
        if slippage_pct > 0.005:
            self.trip(f"SLIPPAGE_{slippage_pct:.4f}")

    def check_liquidation_proximity(self, mark: float, liq_price: float, side_sign: int) -> None:
        # If mark is within 25% of the distance to liquidation, panic.
        if liq_price <= 0:
            return
        buffer = abs(mark - liq_price)
        # side_sign +1 long: liq below mark. Distance is mark-liq.
        # We compare current buffer to entry distance, but here we just
        # trip if the buffer is small enough relative to a reasonable band.
        # Concretely: if the buffer is < 25% of a 5% band.
        rel = buffer / mark
        if rel < 0.0125:  # under 1.25% away
            self.trip("LIQ_PROXIMITY")
