-- moha SQLite journal schema. See DESIGN.md §N.
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
