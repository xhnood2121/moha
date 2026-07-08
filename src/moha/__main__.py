"""moha CLI entry point.

Usage:
    python -m moha --mode backtest --config config/config.yaml --data data/btcusdt_1m.parquet
    python -m moha --mode paper    --config config/config.yaml
    python -m moha --mode live     --config config/config.yaml
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import List

from .config import load_config, load_secrets
from .risk.position_sizer import SymbolFilters
from .runtime import run_live, run_paper
from .types import Candle
from .utils.logger import get_logger, setup_logging

log = get_logger("moha.main")


def _load_candles_parquet(path: str) -> List[Candle]:
    import pandas as pd

    df = pd.read_parquet(path)
    df = df.sort_values("ts").reset_index(drop=True)
    out: List[Candle] = []
    for _, row in df.iterrows():
        out.append(
            Candle(
                ts=int(row["ts"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
                taker_buy_volume=float(row.get("taker_buy_volume", 0.0)),
                closed=True,
            )
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser("moha")
    ap.add_argument("--mode", choices=["backtest", "paper", "live"], default=None,
                    help="Override config.mode.")
    ap.add_argument("--config", required=True)
    ap.add_argument("--data", help="Path to 1m parquet file (backtest only)")
    ap.add_argument("--env", default="config/.env")
    ap.add_argument("--log-level", default="INFO")
    ap.add_argument("--starting-equity", type=float, default=10_000.0)
    args = ap.parse_args()

    setup_logging(args.log_level)
    cfg = load_config(args.config)
    if args.mode:
        cfg.mode = args.mode
    secrets = load_secrets(args.env)
    log.info("boot", mode=cfg.mode, venue=cfg.venue, symbol=cfg.symbol,
             config_hash=cfg.config_hash())

    if cfg.mode == "backtest":
        if not args.data:
            log.error("backtest.needs.data")
            return 2
        from .backtest.engine import run_backtest
        candles = _load_candles_parquet(args.data)
        log.info("backtest.candles", n=len(candles))
        result = run_backtest(cfg, candles, starting_equity=args.starting_equity)
        print(json.dumps(result.metrics.as_dict(), indent=2))
        return 0

    if cfg.mode == "paper":
        asyncio.run(run_paper(cfg, secrets, starting_equity=args.starting_equity))
        return 0

    if cfg.mode == "live":
        if not secrets["api_key"] or not secrets["api_secret"]:
            log.critical("live.no_keys")
            return 3
        asyncio.run(run_live(cfg, secrets))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
