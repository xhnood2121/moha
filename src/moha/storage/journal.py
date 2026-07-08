"""SQLite journal — DESIGN.md §N.

Every signal, trade, order, fill, and event is written here. This is
the source of truth for post-hoc audit.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import aiosqlite

from ..types import EngineName, ExitReason, RegimeSnapshot, Side, Trade


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS equity_snapshots (
    ts             INTEGER PRIMARY KEY,
    wallet_usdt    REAL NOT NULL,
    equity_usdt    REAL NOT NULL,
    unrealized_pnl REAL NOT NULL,
    mode           TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS signals (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             INTEGER NOT NULL,
    engine         TEXT NOT NULL,
    side           TEXT NOT NULL,
    entry_ref      REAL NOT NULL,
    stop_ref       REAL NOT NULL,
    tp1_ref        REAL NOT NULL,
    tp2_ref        REAL,
    score          REAL NOT NULL,
    regime_snap    TEXT NOT NULL,
    filter_results TEXT NOT NULL,
    accepted       INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS trades (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id      INTEGER REFERENCES signals(id),
    open_ts        INTEGER NOT NULL,
    close_ts       INTEGER,
    side           TEXT NOT NULL,
    engine         TEXT NOT NULL,
    entry_price    REAL NOT NULL,
    stop_price     REAL NOT NULL,
    tp1_price      REAL NOT NULL,
    tp2_price      REAL,
    qty            REAL NOT NULL,
    risk_pct       REAL NOT NULL,
    r_multiple     REAL,
    pnl_usdt       REAL,
    fees_usdt      REAL,
    funding_usdt   REAL,
    exit_reason    TEXT,
    max_favorable  REAL,
    max_adverse    REAL,
    notes          TEXT
);
CREATE TABLE IF NOT EXISTS orders (
    client_id      TEXT PRIMARY KEY,
    exchange_id    INTEGER,
    trade_id       INTEGER REFERENCES trades(id),
    ts_placed      INTEGER NOT NULL,
    ts_updated     INTEGER,
    side           TEXT NOT NULL,
    type           TEXT NOT NULL,
    price          REAL,
    stop_price     REAL,
    qty            REAL NOT NULL,
    status         TEXT NOT NULL,
    reduce_only    INTEGER NOT NULL,
    role           TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fills (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             INTEGER NOT NULL,
    client_id      TEXT REFERENCES orders(client_id),
    price          REAL NOT NULL,
    qty            REAL NOT NULL,
    fee_usdt       REAL NOT NULL,
    liquidity      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             INTEGER NOT NULL,
    level          TEXT NOT NULL,
    category       TEXT NOT NULL,
    message        TEXT NOT NULL,
    payload        TEXT
);
CREATE INDEX IF NOT EXISTS idx_signals_ts    ON signals(ts);
CREATE INDEX IF NOT EXISTS idx_trades_open   ON trades(open_ts);
CREATE INDEX IF NOT EXISTS idx_orders_trade  ON orders(trade_id);
CREATE INDEX IF NOT EXISTS idx_events_ts     ON events(ts);
"""


class Journal:
    def __init__(self, path: str):
        self.path = path
        self._db: Optional[aiosqlite.Connection] = None

    async def open(self) -> None:
        Path(os.path.dirname(self.path) or ".").mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.path)
        await self._db.executescript(SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def log_event(self, ts: int, level: str, category: str, message: str, payload: dict | None = None) -> None:
        assert self._db is not None
        await self._db.execute(
            "INSERT INTO events(ts,level,category,message,payload) VALUES (?,?,?,?,?)",
            (ts, level, category, message, json.dumps(payload or {})),
        )
        await self._db.commit()

    async def log_signal(
        self,
        ts: int,
        engine: EngineName,
        side: Side,
        entry_ref: float,
        stop_ref: float,
        tp1_ref: float,
        tp2_ref: Optional[float],
        score: float,
        regime: RegimeSnapshot,
        filter_reasons: list,
        accepted: bool,
    ) -> int:
        assert self._db is not None
        cur = await self._db.execute(
            """
            INSERT INTO signals(ts,engine,side,entry_ref,stop_ref,tp1_ref,tp2_ref,score,
                                regime_snap,filter_results,accepted)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                ts,
                engine.value,
                side.value,
                entry_ref,
                stop_ref,
                tp1_ref,
                tp2_ref,
                score,
                json.dumps(regime.as_dict()),
                json.dumps({"reasons": filter_reasons}),
                1 if accepted else 0,
            ),
        )
        sid = cur.lastrowid
        await self._db.commit()
        return sid

    async def log_trade(self, trade: Trade, signal_id: Optional[int]) -> int:
        assert self._db is not None
        cur = await self._db.execute(
            """
            INSERT INTO trades(signal_id,open_ts,close_ts,side,engine,entry_price,
                               stop_price,tp1_price,tp2_price,qty,risk_pct,r_multiple,
                               pnl_usdt,fees_usdt,funding_usdt,exit_reason,
                               max_favorable,max_adverse,notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                signal_id,
                trade.open_ts,
                trade.close_ts,
                trade.side.value,
                trade.engine.value,
                trade.entry_price,
                trade.stop_price,
                trade.tp1_price,
                trade.tp2_price,
                trade.qty,
                trade.risk_pct,
                trade.r_multiple,
                trade.pnl_usdt,
                trade.fees_usdt,
                trade.funding_usdt,
                trade.exit_reason.value if trade.exit_reason else None,
                trade.max_favorable,
                trade.max_adverse,
                None,
            ),
        )
        tid = cur.lastrowid
        trade.id = tid
        await self._db.commit()
        return tid

    async def snapshot_equity(self, ts: int, wallet: float, equity: float, unrealized: float, mode: str) -> None:
        assert self._db is not None
        await self._db.execute(
            "INSERT OR REPLACE INTO equity_snapshots(ts,wallet_usdt,equity_usdt,unrealized_pnl,mode) VALUES (?,?,?,?,?)",
            (ts, wallet, equity, unrealized, mode),
        )
        await self._db.commit()
