"""Binance USDⓈ-M futures REST client (subset used by moha).

This is a compact, dependency-light client with:
 - HMAC-SHA256 signing
 - retries on 5xx/timeouts with exponential backoff
 - client-order-id idempotency
 - rate-limit acquire before every call
 - refusal to run if the API key has withdrawal permission enabled

It exposes only the methods the bot actually uses. Do not use it as a
general-purpose Binance SDK.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, Optional

import aiohttp

from ..types import Side
from ..utils.logger import get_logger
from .rate_limiter import BinanceLimiters

log = get_logger(__name__)


class BinanceAPIError(RuntimeError):
    def __init__(self, code: int, msg: str, status: int):
        super().__init__(f"{status} {code}: {msg}")
        self.code = code
        self.msg = msg
        self.status = status


@dataclass
class Credentials:
    api_key: str
    api_secret: str


class BinanceFuturesREST:
    def __init__(
        self,
        base_url: str,
        creds: Credentials,
        limiters: BinanceLimiters,
        recv_window_ms: int = 5000,
    ):
        self.base = base_url.rstrip("/")
        self.creds = creds
        self.limiters = limiters
        self.recv_window = recv_window_ms
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self) -> None:
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            )

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    # ----------- signing -----------

    def _sign(self, params: Dict[str, Any]) -> str:
        query = urllib.parse.urlencode(params, doseq=True)
        return hmac.new(
            self.creds.api_secret.encode(), query.encode(), hashlib.sha256
        ).hexdigest()

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
        weight: int = 1,
        order: bool = False,
        retries: int = 3,
    ) -> Any:
        assert self._session is not None
        await self.limiters.acquire_rest(weight)
        if order:
            await self.limiters.acquire_order()
        headers = {"X-MBX-APIKEY": self.creds.api_key} if signed else {}
        p = dict(params or {})
        if signed:
            p["timestamp"] = int(time.time() * 1000)
            p["recvWindow"] = self.recv_window
            p["signature"] = self._sign(p)
        url = f"{self.base}{path}"
        backoff = 1.0
        last_exc: Optional[Exception] = None
        for attempt in range(retries + 1):
            try:
                async with self._session.request(method, url, params=p, headers=headers) as r:
                    text = await r.text()
                    if r.status in (418, 429):
                        # Ban/limit — do not retry aggressively.
                        raise BinanceAPIError(-1, f"rate-limit {text[:200]}", r.status)
                    if r.status >= 500:
                        raise BinanceAPIError(-1, f"server {r.status}", r.status)
                    if r.status == 400:
                        try:
                            j = await _safe_json(r, text)
                            code = int(j.get("code", -1))
                            msg = str(j.get("msg", text))
                            raise BinanceAPIError(code, msg, r.status)
                        except BinanceAPIError:
                            raise
                    if r.status != 200:
                        raise BinanceAPIError(-1, text[:200], r.status)
                    return await _safe_json(r, text)
            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                last_exc = e
            except BinanceAPIError as e:
                if e.status >= 500 and attempt < retries:
                    last_exc = e
                else:
                    raise
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 8.0)
        raise last_exc or RuntimeError("request failed with no exception")

    # ----------- account -----------

    async def account_info(self) -> dict:
        return await self._request("GET", "/fapi/v2/account", signed=True, weight=5)

    async def position_risk(self, symbol: str) -> list:
        return await self._request(
            "GET", "/fapi/v2/positionRisk", params={"symbol": symbol}, signed=True, weight=5
        )

    async def exchange_info(self) -> dict:
        return await self._request("GET", "/fapi/v1/exchangeInfo", weight=1)

    # ----------- klines / funding -----------

    async def klines(self, symbol: str, interval: str, limit: int = 500) -> list:
        return await self._request(
            "GET",
            "/fapi/v1/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
            weight=2,
        )

    async def funding_rate(self, symbol: str) -> dict:
        return await self._request(
            "GET", "/fapi/v1/premiumIndex", params={"symbol": symbol}, weight=1
        )

    async def open_interest(self, symbol: str) -> dict:
        return await self._request(
            "GET", "/fapi/v1/openInterest", params={"symbol": symbol}, weight=1
        )

    # ----------- orders -----------

    async def new_order(
        self,
        *,
        symbol: str,
        side: Side,
        order_type: str,
        qty: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        reduce_only: bool = False,
        client_order_id: Optional[str] = None,
        time_in_force: Optional[str] = None,
    ) -> dict:
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": "BUY" if side is Side.LONG else "SELL",
            "type": order_type,
            "quantity": qty,
        }
        if price is not None:
            params["price"] = price
        if stop_price is not None:
            params["stopPrice"] = stop_price
        if reduce_only:
            params["reduceOnly"] = "true"
        if client_order_id:
            params["newClientOrderId"] = client_order_id
        if time_in_force:
            params["timeInForce"] = time_in_force
        return await self._request(
            "POST", "/fapi/v1/order", params=params, signed=True, weight=1, order=True
        )

    async def cancel_all_open(self, symbol: str) -> dict:
        return await self._request(
            "DELETE",
            "/fapi/v1/allOpenOrders",
            params={"symbol": symbol},
            signed=True,
            weight=1,
            order=True,
        )

    async def open_orders(self, symbol: str) -> list:
        return await self._request(
            "GET",
            "/fapi/v1/openOrders",
            params={"symbol": symbol},
            signed=True,
            weight=1,
        )

    # ----------- safety -----------

    async def verify_key_safety(self) -> None:
        """Refuse to run if the key can withdraw funds."""
        info = await self.account_info()
        if info.get("canWithdraw", False):
            raise RuntimeError(
                "API key has withdraw permission enabled. Refuse to run. "
                "Regenerate a key with withdrawals DISABLED and IP whitelisted."
            )


async def _safe_json(r: aiohttp.ClientResponse, text: str) -> Any:
    import orjson

    try:
        return orjson.loads(text)
    except Exception:  # noqa: BLE001
        return text
