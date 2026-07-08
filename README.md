# moha — Aggressive BTCUSDT Bot for Binance

**Educational / research code. Not financial advice. Trading crypto with
leverage can and does destroy accounts. Do not run this bot with real
money without completing the full validation gate in `DESIGN.md` (Q → S).**

`moha` is an aggressive-but-controlled BTC intraday bot targeting
Binance USDⓈ-M perpetual futures (BTCUSDT). It runs three signal engines
— momentum breakout, pullback continuation, and volatility expansion —
gated by a regime router, Binance-specific microstructure filters, and
a strict risk engine with a hard kill-switch.

## What lives where

- **`DESIGN.md`** — the complete design document. Read this first. It
  covers Phases 1–11 and deliverables A–U: feasibility, spot vs
  futures, market behavior, strategy engines, entry/exit rules, risk
  model, sizing, architecture, DB schema, pseudocode, backtest plan,
  paper plan, live rollout, failure modes.
- **`src/moha/`** — the Python package.
- **`config/config.example.yaml`** — copy to `config/config.yaml` and edit.
- **`config/.env.example`** — copy to `config/.env`, `chmod 600`, fill.
- **`schema.sql`** — SQLite journal schema (also embedded in code).
- **`tests/`** — unit tests for indicators, sizing, and engines.

## Quick start (paper-trading dev loop)

```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config/config.example.yaml config/config.yaml
cp config/.env.example config/.env && chmod 600 config/.env
python -m moha --mode paper --config config/config.yaml
```

Backtest a saved parquet of 1m klines:

```
python -m moha --mode backtest --config config/config.yaml \
    --data data/btcusdt_1m.parquet
```

Live (only after Q, R, and S in `DESIGN.md` are complete):

```
python -m moha --mode live --config config/config.yaml
```

## Non-negotiable safety rules baked in

- No martingale. No averaging down. No pyramiding.
- Max effective leverage 5×, isolated margin only.
- Per-trade risk clamped to `[0.5%, 1.5%]`; auto-reduces after losses.
- Daily loss cap 3%, weekly 7%, drawdown-from-ATH kill at 10%.
- The bot refuses to start if the API key has withdraw permission.
- The bot refuses to run live until a paper-log config hash matches
  the current config hash (48h paper gate).

## Tests

```
pytest -q
```

Read `DESIGN.md` before touching the code. The doc is the spec.
