"""Leaky-bucket rate limiters for request weight and order counts."""
from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Deque


class WindowLimiter:
    """Sliding-window counter over `window_sec` seconds with a `cap` budget."""

    def __init__(self, cap: int, window_sec: float):
        self.cap = cap
        self.window = window_sec
        self._events: Deque[tuple[float, int]] = deque()
        self._lock = asyncio.Lock()

    def _trim(self, now: float) -> int:
        cutoff = now - self.window
        while self._events and self._events[0][0] < cutoff:
            self._events.popleft()
        return sum(w for _, w in self._events)

    async def acquire(self, weight: int = 1) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                used = self._trim(now)
                if used + weight <= self.cap:
                    self._events.append((now, weight))
                    return
                # Wait until oldest event exits the window.
                oldest = self._events[0][0]
                sleep_for = max(0.05, oldest + self.window - now)
                await asyncio.sleep(sleep_for)


class BinanceLimiters:
    def __init__(self, rest_weight_per_min: int, orders_per_10s: int):
        self.rest = WindowLimiter(rest_weight_per_min, 60.0)
        self.orders = WindowLimiter(orders_per_10s, 10.0)

    async def acquire_rest(self, weight: int = 1) -> None:
        await self.rest.acquire(weight)

    async def acquire_order(self) -> None:
        await self.orders.acquire(1)
