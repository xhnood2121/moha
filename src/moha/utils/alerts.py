"""Alert sinks. Telegram is the primary channel; stdout is the fallback."""
from __future__ import annotations

import asyncio
from typing import Optional

import aiohttp

from .logger import get_logger

log = get_logger(__name__)


class Alerts:
    def __init__(
        self,
        enabled: bool,
        telegram_token: Optional[str],
        telegram_chat_id: Optional[str],
    ):
        self.enabled = enabled and bool(telegram_token) and bool(telegram_chat_id)
        self.token = telegram_token
        self.chat_id = telegram_chat_id

    async def page(self, category: str, message: str) -> None:
        """Fire an out-of-band alert. Never raises."""
        text = f"[moha][{category}] {message}"
        log.warning("alert", category=category, message=message)
        if not self.enabled:
            return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json={"chat_id": self.chat_id, "text": text},
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as r:
                    if r.status != 200:
                        log.error("telegram.fail", status=r.status)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.error("telegram.exc", err=str(e))
