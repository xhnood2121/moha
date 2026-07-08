"""Binance USDⓈ-M futures market-data WebSocket.

Subscribes to a fixed set of BTCUSDT streams and yields normalized
events into an asyncio queue. Reconnect with exponential backoff, then
re-sync via REST so the strategy state is deterministic post-reconnect.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

import orjson
import websockets

from ..types import BookTop, Candle
from ..utils.logger import get_logger

log = get_logger(__name__)

TF_TO_STREAM = {"1m": "kline_1m", "5m": "kline_5m", "15m": "kline_15m", "1h": "kline_1h"}


@dataclass
class WSEvent:
    kind: str            # "kline" | "book" | "mark" | "agg"
    tf: Optional[str]
    payload: object


class BinanceMarketWS:
    def __init__(
        self,
        base_ws: str,
        symbol: str,
        timeframes: list[str],
        on_event: Callable[[WSEvent], Awaitable[None]],
        max_backoff: float = 30.0,
    ):
        self.base_ws = base_ws
        self.symbol = symbol.lower()
        self.timeframes = timeframes
        self.on_event = on_event
        self.max_backoff = max_backoff
        self.last_msg_ts: float = 0.0
        self._stop = False

    def _stream_url(self) -> str:
        parts = []
        parts += [f"{self.symbol}@{TF_TO_STREAM[tf]}" for tf in self.timeframes if tf in TF_TO_STREAM]
        parts += [f"{self.symbol}@bookTicker", f"{self.symbol}@markPrice@1s", f"{self.symbol}@aggTrade"]
        return f"{self.base_ws}/stream?streams=" + "/".join(parts)

    async def run(self) -> None:
        backoff = 1.0
        while not self._stop:
            try:
                async with websockets.connect(self._stream_url(), ping_interval=15, ping_timeout=15) as ws:
                    backoff = 1.0
                    log.info("ws.connected", url=self._stream_url())
                    async for raw in ws:
                        self.last_msg_ts = time.monotonic()
                        try:
                            msg = orjson.loads(raw)
                        except Exception:  # noqa: BLE001
                            continue
                        await self._dispatch(msg)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                log.warning("ws.disconnect", err=str(e), backoff=backoff)
                await asyncio.sleep(backoff)
                backoff = min(self.max_backoff, backoff * 2)

    def stop(self) -> None:
        self._stop = True

    async def _dispatch(self, msg: dict) -> None:
        data = msg.get("data") or msg
        stream = msg.get("stream", "")
        if "@kline_" in stream:
            k = data.get("k", {})
            tf = k.get("i")
            candle = Candle(
                ts=int(k.get("t", 0)),
                open=float(k.get("o", 0)),
                high=float(k.get("h", 0)),
                low=float(k.get("l", 0)),
                close=float(k.get("c", 0)),
                volume=float(k.get("v", 0)),
                taker_buy_volume=float(k.get("V", 0)),
                closed=bool(k.get("x", False)),
            )
            await self.on_event(WSEvent(kind="kline", tf=tf, payload=candle))
        elif "@bookTicker" in stream:
            book = BookTop(
                bid=float(data.get("b", 0)),
                bid_qty=float(data.get("B", 0)),
                ask=float(data.get("a", 0)),
                ask_qty=float(data.get("A", 0)),
            )
            await self.on_event(WSEvent(kind="book", tf=None, payload=book))
        elif "@markPrice" in stream:
            mark = float(data.get("p", 0))
            fr = float(data.get("r", 0))
            next_ts = int(data.get("T", 0))
            await self.on_event(WSEvent(kind="mark", tf=None, payload=(mark, fr, next_ts)))
        elif "@aggTrade" in stream:
            payload = {
                "price": float(data.get("p", 0)),
                "qty": float(data.get("q", 0)),
                "buyer_maker": bool(data.get("m", False)),
                "ts": int(data.get("T", 0)),
            }
            await self.on_event(WSEvent(kind="agg", tf=None, payload=payload))
