# BTC-BINANCE-BOT — Aggressive but Controlled BTCUSDT Intraday System

> Educational / research design. Not financial advice. Trading crypto with
> leverage can and does destroy accounts. Never deploy without the full
> validation gate described in Section Q/R/S.

---

## Table of Contents

- [A. Binance Feasibility Analysis](#a-binance-feasibility-analysis)
- [B. Spot vs Futures Recommendation](#b-spot-vs-futures-recommendation)
- [C. BTC Market Behavior on Binance](#c-btc-market-behavior-on-binance)
- [D. Final Aggressive Strategy](#d-final-aggressive-strategy)
- [E. Strategy Engines](#e-strategy-engines)
- [F. Binance-Specific Filters](#f-binance-specific-filters)
- [G. Exact Long Rules](#g-exact-long-rules)
- [H. Exact Short Rules](#h-exact-short-rules)
- [I. Exit System](#i-exit-system)
- [J. Risk Management Rules](#j-risk-management-rules)
- [K. Position Sizing Formula](#k-position-sizing-formula)
- [L. Capital Allocation Model](#l-capital-allocation-model)
- [M. Bot Architecture](#m-bot-architecture)
- [N. Database Schema](#n-database-schema)
- [O. Pseudocode](#o-pseudocode)
- [P. Python Implementation Plan](#p-python-implementation-plan)
- [Q. Backtesting Plan](#q-backtesting-plan)
- [R. Paper Trading Plan](#r-paper-trading-plan)
- [S. Live Deployment Rules](#s-live-deployment-rules)
- [T. Failure Scenarios & Protection](#t-failure-scenarios--protection)
- [U. Final Recommendation](#u-final-recommendation)

---

## A. Binance Feasibility Analysis

### A.1 BTCUSDT liquidity (both venues)

- **Spot BTC/USDT**: top-3 deepest crypto book in the world.
  Typical top-of-book size in mid-2024–2026 is 0.5–5 BTC per side,
  with $10M+ of resting depth within ±0.10% of mid. Spread is
  routinely 0.01 USDT (1 tick) in calm regimes; it widens by 5–20×
  during news candles and liquidation cascades.
- **USDⓈ-M Futures BTCUSDT (perp)**: even deeper than spot for
  intraday flow. Perp routinely does $30–80B/day notional. Top-of-book
  is generally 1–20 BTC per side; the top 10 levels hold hundreds of
  BTC. Spread is normally 0.10 USDT (1 tick).
- **Implication**: For a bot risking <=1.5% of a five- to seven-figure
  account per trade, both books can absorb entry/exit without material
  price impact. Liquidity is not the bottleneck — decision quality is.

### A.2 Fees (as of the 2024–2026 fee schedule; check dashboard before go-live)

| Venue    | Maker (VIP 0) | Taker (VIP 0) | BNB discount | Notes |
|----------|--------------:|--------------:|-------------:|-------|
| Spot     | 0.1000%       | 0.1000%       | −25%         | 0.075% eff. w/ BNB |
| USDⓈ-M   | 0.0200%       | 0.0500%       | −10%         | 0.018% / 0.045% eff. |
| COIN-M   | 0.0100%       | 0.0500%       | −10%         | Inverse; ignore |

- Round-trip taker cost, USDⓈ-M w/ BNB = ~0.09%. Round-trip taker cost,
  Spot w/ BNB = ~0.15%. This ~6 bp/trade difference is *material* for
  an intraday system doing 3–15 trades per session.

### A.3 Funding rates (futures only)

- Paid every 8 hours (00:00, 08:00, 16:00 UTC).
- Normal range: −0.01% to +0.02% per interval (roughly ±0.03%/day).
- Extreme regimes: ±0.1% per interval sustained can appear during
  euphoric or capitulation phases.
- **Rule**: The bot must (a) log the funding schedule, (b) *never* hold
  an unhedged directional position across a funding print when the
  predicted funding is >|0.05%|, unless the trade thesis explicitly
  benefits from it (short in overheated longs regime, etc.).

### A.4 Leverage & liquidation

- Max leverage on BTCUSDT perp is 125× isolated for low tiers, but
  above 20× the maintenance margin ratio and forced-deleveraging risk
  make this unsuitable for any strategy. The bot caps notional
  leverage at **5× effective**.
- Liquidation price uses `maintenance_margin_rate` per position
  bracket (0.4% at low notional, rising to 5%+ at large notional).
  The bot must always keep the initial stop **inside** the liquidation
  distance by a margin of at least 5× (i.e. stop distance ≤ 20% of the
  liquidation distance).

### A.5 API limits (as of Binance docs; verify before deploy)

- Spot REST: 1200 request weight / minute per IP, 100 orders / 10 s,
  200,000 orders / 24 h per account.
- Futures REST: 2400 request weight / minute per IP, 300 orders / 10 s
  per account.
- WebSocket: 5 messages / second per connection, 24 h max lifetime,
  auto-disconnect after 24 h.
- Order book snapshots: up to 5000 levels via REST; live diffs via WS
  `depth@100ms` or `depth@1000ms`.

### A.6 Order types the bot uses

- `LIMIT` (post-only via `timeInForce=GTX` on futures) for maker entries.
- `MARKET` for panic-exit and momentum entries when the edge is speed.
- `STOP_MARKET` / `TAKE_PROFIT_MARKET` for stop and take-profit.
- `TRAILING_STOP_MARKET` — supported on futures, useful but the callback
  is percent-based; the bot implements its own ATR-based trailing on
  top of the exchange trailing for robustness.
- **No `OCO` on futures**. The bot enforces OCO semantics itself
  through the order manager.

### A.7 Slippage, spread, latency

- Slippage: assumed 0.5–1.5 ticks on market entries in normal regime;
  3–10 ticks during news candles. The backtester models this as
  `spread/2 + k * ATR%` with `k` learned from paper trading.
- Latency: colocated in `ap-northeast-1` (Tokyo, matching Binance's
  primary region), round-trip is ~5–15 ms. A retail VPS in another
  region will see 60–250 ms. The strategy is designed to be *not*
  latency-sensitive at the entry (uses 1m and 5m signals); latency
  matters only for the emergency exit path, which is why the
  kill-switch uses `MARKET` orders.

### A.8 Verdict

Binance is feasible and appropriate. The main risk vectors are (a)
funding surprises, (b) API rate-limit stalls during volatility, and
(c) partial-fill cascades during liquidations. All three are addressed
explicitly in Section M and T.

---

## B. Spot vs Futures Recommendation

### B.1 Comparison matrix

| Dimension              | Spot                        | USDⓈ-M Futures                        |
|------------------------|-----------------------------|---------------------------------------|
| Direction              | Long-only                   | Long AND short                        |
| Fees round-trip        | ~0.15%                      | ~0.09%                                |
| Leverage               | None (or 3–5× via margin)   | Up to 125× (bot caps at 5×)           |
| Funding                | None                        | ±0.01%–0.05% per 8h                   |
| Liquidation risk       | None (spot can't liquidate) | Yes                                   |
| Order features         | OCO                         | Reduce-only, hedge mode, trailing stop|
| Depth (intraday flow)  | Deep                        | Deeper                                |
| Regulatory clarity     | Cleaner in most regions     | Restricted in US, UK, several EU      |

### B.2 Recommendation: **USDⓈ-M Futures (BTCUSDT perp) as primary**

Reasons:

1. **Shorts.** Intraday BTC spends 45–55% of its time in defined
   downtrends. A long-only spot bot leaves half the edge on the table
   and is forced to sit through the exact regimes where volatility is
   highest.
2. **Lower fees.** ~6 bp/round trip cheaper. Over 100 trades that is
   6% of gross P&L reclaimed.
3. **Controlled leverage.** Capping at 5× effective still gives room
   to size properly on a $1k–$50k account without hitting notional
   minimums. Spot cannot do this without wire-scale capital.
4. **Better exit primitives.** `reduce-only` guarantees the bot never
   accidentally flips direction when scaling out.

### B.3 Where Spot wins (and when to fall back)

Fall back to Spot BTCUSDT only if:

- The operator is in a jurisdiction that prohibits futures (US retail,
  UK retail, Ontario). The bot must refuse to start in `futures` mode
  when the country code from account info is on that list.
- The strategy is being run at low capital (<$500) where spot's
  no-liquidation floor is safer than the futures margin math.

The codebase supports both venues via the `Exchange` abstraction so
this fallback is a config flag, not a rewrite.

### B.4 Effective leverage cap

**Effective leverage = position notional / account equity.**

The bot uses `notional_leverage <= 5x` with the following ladder:

| Regime score (see F.5) | Max effective leverage |
|-----------------------:|-----------------------:|
| 0.8–1.0 (very strong)  | 5.0×                   |
| 0.6–0.8                | 3.5×                   |
| 0.4–0.6                | 2.0×                   |
| < 0.4                  | 1.0× or trade disabled |

Isolated margin only. Cross margin is disabled because a single bad
trade must never touch other collateral.

---

## C. BTC Market Behavior on Binance

### C.1 Session structure (UTC)

| Session         | UTC window   | Characteristic                                       |
|-----------------|--------------|------------------------------------------------------|
| Asia            | 00:00–07:00  | Low volume, drift, mean-reverting                    |
| London          | 07:00–13:00  | Rising volume, trend initiation, false breaks        |
| London/NY overlap | 13:00–16:00 | **Highest volatility**, cleanest trends              |
| NY afternoon    | 16:00–21:00  | Continuation or reversal of NY morning move          |
| Off-hours       | 21:00–00:00  | Position squaring, thin liquidity, whipsaws          |
| Weekend         | Fri 22:00 UTC → Mon 00:00 UTC | Thin, higher fake-break rate, funding fund-flow effects |

The regime engine biases size and engine selection by session (see F.5).

### C.2 Volatility structures the bot exploits

- **Asia range → London breakout.** Roughly 40% of trading days show
  a tight Asia range followed by a directional London expansion.
  Volatility expansion engine focuses here.
- **NY continuation.** When London prints a clean trend, NY continues
  it 55–60% of the time until 18:00 UTC. Pullback engine focuses here.
- **Liquidation cascade.** Fast >0.7% adverse moves in <30 s across
  the perp trigger stop-loss + liquidation dominoes; a follow-through
  candle in the same direction has 70%+ historical continuation for
  the next 3–15 minutes. Momentum engine focuses here.

### C.3 Structures the bot *avoids*

- **Fake breakouts around round numbers.** BTC pings $2k round numbers
  and immediately reverses ~35% of the time. Filter F.4 catches this
  by requiring volume confirmation and a close beyond the round.
- **Stop hunts.** 3–8 tick wick-outs of the prior 15m/1h low/high that
  return inside the range within 2 candles. Filter F.6 requires closed
  candle confirmation, not intra-candle.
- **News candles.** Fed / CPI / SEC decisions produce 1–5% candles with
  1–2% wicks. The volatility filter (F.3) disables new entries when
  1m ATR exceeds 2× its 20-period median.
- **Weekend chop.** Fri 22:00 UTC → Mon 00:00 UTC gets max size cut to
  50% and momentum engine gate raised.

### C.4 Funding-rate influence

- Persistent funding > +0.03% per 8h → longs are crowded → mean-reversion
  shorts have edge. Bot's short engine gets +5% score boost.
- Persistent funding < −0.03% per 8h → shorts crowded → long squeezes
  are richer. Bot's long momentum engine gets +5% score boost.

---

## D. Final Aggressive Strategy

**BTCUSDT intraday, three-engine hybrid, regime-gated, on USDⓈ-M perp
with 5× effective leverage cap.**

- Primary decision candle: 5m close (main engine trigger).
- Fast confirmation candle: 1m (entry timing, exit trailing).
- Higher timeframe context: 15m and 1h EMA/ADX for trend gate.
- Signal cadence: signals evaluated on every 5m close, entries actioned
  on 1m close after confirmation, exits monitored on 1m and streamed
  from `bookTicker` for the emergency path.
- Reward-to-risk (R:R) minimum: 1.8 : 1 on Momentum, 1.5 : 1 on Pullback,
  2.0 : 1 on Expansion. Trades below these thresholds are skipped.
- Max concurrent positions: 1. Aggressive but not cowboy — pyramiding
  is disabled; there is one BTC position at a time.
- Session bias: bot is most active 07:00–21:00 UTC. Off-hours require a
  much stronger score to fire.

---

## E. Strategy Engines

Each engine outputs `EngineSignal(side, entry_type, entry_price,
stop_price, take_profit_price, score, meta)`. The **regime router**
picks at most one engine per 5m bar to submit to the risk gate.

### E.1 Momentum Breakout Engine (`MomentumEngine`)

Purpose: catch initial expansion off a compressed base or off a
liquidation flush.

Trigger (long variant; short is mirrored):
- Close price breaks the highest high of the last **N=20** completed
  5m candles by ≥ 0.10% AND
- 5m volume ≥ 1.8× the 20-period volume median AND
- Real-body ratio of the trigger candle ≥ 0.55 (not a wick), AND
- 15m EMA(21) > EMA(55) (trend context) AND
- ADX(14, 15m) ≥ 18 (directional environment) AND
- 1m ATR% is not in the top 5% of the last 24h (news-candle filter).

Score `s = 0.5 + 0.5 * min(volume_ratio/3, 1) - 0.2 * distance_to_ema55_pct`.
Higher score → larger size within the regime cap.

Stop: below the low of the trigger candle − 0.15 × ATR(14, 5m).
Take profit 1 (partial 50%): 1.0 R.
Take profit 2 (partial 50%): 2.5 R, then ATR trailing.

### E.2 Pullback Continuation Engine (`PullbackEngine`)

Purpose: buy shallow pullbacks in a defined trend, not late chases.

Trigger (long):
- 1h EMA(21) > EMA(55) AND 15m EMA(21) > EMA(55) (multi-timeframe up)
- 5m price touches EMA(21) OR retraces 38–61% of the last 5m swing.
- The pullback holds above the higher-low pivot from 15m.
- The trigger 5m candle closes bullish with lower wick ≥ 0.3× total range.
- RSI(14, 5m) rebounds from below 40 back above 40.

Score `s = 0.6 + 0.4 * (adx_15m/40)`.

Stop: below the pullback pivot low − 0.2 × ATR(14, 5m).
Take profit 1 (60%): 1.0 R.
Take profit 2 (40%): trailing 2 × ATR after 1.5 R reached.

### E.3 Volatility Expansion Engine (`ExpansionEngine`)

Purpose: catch the first strong expansion after a compression base.

Trigger:
- Bollinger Band width (20, 2σ, 5m) has been below its 40-period 20th
  percentile for at least 6 of the last 10 bars **and**
- 5m candle closes outside the Bollinger Band **and**
- Volume ≥ 1.5× 20-period median **and**
- Body ≥ 0.6× total range **and**
- 15m EMA(21) direction matches the breakout direction OR ADX(14, 15m) ≤ 15
  (breakout from a genuinely flat regime).

Score `s = 0.7 - band_width_pctile + 0.3 * volume_ratio_clamped`.

Stop: opposite Bollinger band OR 1.2 × ATR opposite the breakout,
whichever is tighter.
Take profit 1 (50%): 1.5 R.
Take profit 2 (50%): 3 R or trail.

### E.4 Regime Router

Uses a compact score to pick the engine:
```
regime.trend    = clamp((ema21_1h - ema55_1h) / ema55_1h * 100, -1, 1)
regime.expand   = 1 if bbwidth_pctile < 0.2 else 0
regime.momentum = 1 if adx_15m > 22 and volume_ratio_5m > 1.5 else 0
regime.chop     = 1 if adx_15m < 15 and bbwidth_pctile > 0.6 else 0
```
Router table:

| Condition                             | Engine chosen         |
|---------------------------------------|-----------------------|
| momentum == 1 AND \|trend\| ≥ 0.15    | Momentum              |
| \|trend\| ≥ 0.20 AND momentum == 0    | Pullback              |
| expand == 1                           | Expansion             |
| chop == 1                             | *No trades. Sleep.*   |

If two conditions fire, pick the engine with the higher score.

---

## F. Binance-Specific Filters

Every candidate signal must pass ALL of these to reach the risk engine.

### F.1 Spread filter
Reject if `(ask - bid) / mid > 3 × trailing_1h_median_spread`.

### F.2 Liquidity wall filter
Reject longs if the sum of ask sizes in the first 20 levels above mid
is > 3× the sum of bid sizes in the first 20 levels below mid (i.e.
sellers are dominating the near book). Mirror for shorts.

### F.3 Volatility filter
Reject if `atr_1m_now > 2 × atr_1m_median_24h` — this is a news candle
or panic candle regime. Wait one bar.

### F.4 Round-number proximity filter
Reject if the entry is within 0.1% of a $1000 round number **and** the
last 3 hourly touches of that round rejected (defined as bar closed
back on the other side within 2 candles).

### F.5 Session filter
- 00:00–07:00 UTC and 21:00–00:00 UTC: require `score ≥ 0.75`.
- 07:00–21:00 UTC: require `score ≥ 0.55`.
- Weekend: additionally reduce risk_pct by 50%.

### F.6 Abnormal candle filter
Reject if the trigger candle's total range > 3× the 5m ATR(14). This is
a spike; entering here means becoming the last buyer.

### F.7 Taker pressure filter
For longs, require `taker_buy_ratio_1m > 0.55` (Binance publishes this
via `takerBuyVolume` in the aggregate trade feed). Mirror for shorts.

### F.8 Funding filter
If holding across the next funding print AND
`predicted_funding * direction < −0.05%`, skip entries within the last
5 minutes before funding.

### F.9 Open Interest filter (futures)
Reject if 30-minute OI change is > +5% AND price change is
< +0.2% (rising OI without price = late longs / late shorts). Mirror.

### F.10 Duplicate / cooldown filter
No new entry within 3 × 5m bars (= 15 minutes) after the last entry on
the same side. Prevents choppy re-entries.

---

## G. Exact Long Rules

### G.1 Long — Momentum Breakout
1. Close of current 5m > max(high[t-1..t-20]) × 1.001
2. Vol(5m) ≥ 1.8 × median(vol[t-1..t-20])
3. Body ≥ 0.55 × range(candle)
4. ema21_15m > ema55_15m
5. adx14_15m ≥ 18
6. Filters F.1–F.10 pass
7. Entry = market at 1m close of first confirmation candle whose close
   is above the trigger candle's high
8. Stop = trigger_candle_low − 0.15 × atr14_5m
9. TP1 = entry + 1.0 R (close 50%)
10. TP2 = entry + 2.5 R (close 50%), then trail by 1.5 × atr14_5m
11. Move stop to breakeven after TP1

### G.2 Long — Pullback Continuation
1. ema21_1h > ema55_1h AND ema21_15m > ema55_15m
2. 5m low touches ema21_5m OR retrace = 38–61% of last 5m swing
3. Pullback bottom > last 15m higher-low pivot
4. Trigger candle bullish, lower wick ≥ 0.3 × range
5. RSI(14, 5m) crosses back above 40
6. Filters pass
7. Entry = market at close of trigger candle
8. Stop = pullback_pivot_low − 0.2 × atr14_5m
9. TP1 = entry + 1.0 R (close 60%)
10. TP2 = trail 2 × atr14_5m after 1.5 R
11. Move stop to breakeven after TP1

### G.3 Long — Volatility Expansion
1. bbwidth_5m in bottom 20th percentile for ≥ 6 of last 10 bars
2. Close > upper band
3. Body ≥ 0.6 × range, volume ≥ 1.5 × median
4. Trend context OR flat ADX (see E.3)
5. Filters pass
6. Entry = market at close
7. Stop = min(lower band, entry − 1.2 × atr14_5m)
8. TP1 = entry + 1.5 R (close 50%)
9. TP2 = entry + 3.0 R or trail
10. Breakeven after TP1

---

## H. Exact Short Rules

Mirror of G with sign flips:

### H.1 Short — Momentum Breakdown
1. Close < min(low[t-1..t-20]) × 0.999
2. Vol ≥ 1.8 × median
3. Body ≥ 0.55 × range
4. ema21_15m < ema55_15m, adx14_15m ≥ 18
5. Filters pass
6. Entry = market at 1m close breaking below trigger low
7. Stop = trigger_high + 0.15 × atr14_5m
8. TP1 = entry − 1.0 R (50%), TP2 = entry − 2.5 R (50%) then trail

### H.2 Short — Pullback Continuation Down
1. ema21_1h < ema55_1h AND ema21_15m < ema55_15m
2. 5m high touches ema21_5m OR retrace 38–61% of last 5m down-swing
3. Pullback top < last 15m lower-high pivot
4. Trigger candle bearish, upper wick ≥ 0.3 × range
5. RSI(14, 5m) crosses back below 60
6. Filters pass
7. Entry / stop / TPs mirrored

### H.3 Short — Volatility Expansion Down
Mirror of G.3 with close below lower band.

**Short-specific extra filter**: if funding is < −0.05%, require
`score ≥ 0.7` (short-crowded regimes squeeze).

---

## I. Exit System

Every open trade has ALL of these exit hooks live in parallel; whichever
fires first wins.

### I.1 Fixed partial take profit
As specified per engine: TP1 closes 50–60%, TP2 closes remainder.

### I.2 Trailing stop
Once TP1 is hit, stop is moved to breakeven. Once 1.5 R (or engine-
specific level) is reached on the runner, an ATR-based trailing stop
takes over: `trail = last_high - k * atr14_5m` for longs.
`k = 1.5` for Momentum/Pullback, `k = 2.0` for Expansion.

### I.3 Break-even automation
Triggered by TP1 fill event. Stop is moved to `entry ± 1 tick` in
the profitable direction. Uses a `STOP_MARKET` reduce-only order.

### I.4 Failure exit
If price hits stop, exit is market reduce-only. No "hoping" bar.

### I.5 Time-based exit
If price has not reached TP1 within `T_max` bars, exit market:
- Momentum: 12 × 5m bars (1h)
- Pullback: 18 × 5m bars (1.5h)
- Expansion: 24 × 5m bars (2h)

### I.6 Emergency exit / kill-switch
Triggered if:
- Daily loss cap hit (see J.2)
- WebSocket disconnect > 10s AND open position exists
- REST error rate > 10% in trailing 60s
- Exchange returns `-2019` (margin insufficient) or `-4131` (percentage
  price protection) unexpectedly.

Emergency exit sends **reduce-only MARKET** on both sides; if fills are
partial, retries every 500 ms up to 10 times, then pages the operator.

### I.7 Volatility collapse exit
If ATR(14, 5m) collapses to < 40% of its value at entry AND price is
< 0.5 R positive, exit market. The move has died.

### I.8 Opposite signal exit
If the router flips to an opposite-side, `score ≥ 0.7` signal while a
position is open, close current position market and go flat. Do NOT
auto-flip; require one bar of no-position between flips.

---

## J. Risk Management Rules

### J.1 Per-trade risk

- Base risk = **0.75%** of equity per trade.
- Range: **0.5% (defensive) → 1.5% (max)**.
- Signal score maps to risk:
  - score ≥ 0.85 AND regime score ≥ 0.75 → 1.25%–1.5%
  - score in [0.65, 0.85) → 0.75%–1.0%
  - score in [0.55, 0.65) → 0.5%
  - score < 0.55 → skip.

### J.2 Daily / weekly caps

- Max realized loss per day: **3.0%** of equity. Bot shuts down until
  next UTC day rollover.
- Max realized loss per week: **7.0%**. Bot enters `COOLDOWN` mode; only
  paper trades until Monday.
- Max consecutive losing trades: **4**. Bot halves `base_risk_pct`
  until it prints a winner; then restores.

### J.3 Position limits

- Max concurrent positions: **1** (BTCUSDT only).
- Max effective leverage: **5×** (see B.4 ladder).
- No pyramiding.

### J.4 Volatility-adjusted stop

Stop distance is *always* expressed in ATR multiples, not fixed %:
`stop_distance = k_engine * atr14_5m + buffer_ticks`.
Position size is derived from stop distance so that `loss_at_stop = risk_pct * equity`.

### J.5 Reduce after losses

After each loss, `effective_risk_pct *= 0.85` until a win resets it.
Floor at 0.4%. This is a Kelly-fractional style reducer, not a
martingale.

### J.6 Scale up only after proven positive conditions

`effective_risk_pct` can rise back toward base only after (a) 3
consecutive net-positive trading days AND (b) trailing 30-trade
profit factor > 1.4.

### J.7 Hard kill-switch

Any of:
- Equity drawdown from all-time high ≥ **10%**.
- Any single trade slippage > 0.5% of notional.
- Two consecutive failed emergency exits.
- Operator sends `KILL` via alert channel.

Kill-switch = flatten, cancel all, disable trading, page operator, do
not resume without human ack.

### J.8 What is banned

- No martingale.
- No averaging down / DCA into losers.
- No unlimited leverage.
- No overriding stops manually via console while the bot runs.
- No trading during scheduled Binance maintenance windows.

---

## K. Position Sizing Formula

Given:
- `E` = account equity (USDT).
- `r` = effective risk pct (fraction, e.g. 0.0075).
- `P_entry`, `P_stop`, `contract_size = 1` for USDⓈ-M BTC perp
  (each contract = 1 USDT of quoted value change per $1 move on
  quantity 1 BTC; the venue uses `quantity` in BTC).

Formula (USDⓈ-M linear perp):
```
risk_usdt      = E * r
stop_distance  = |P_entry - P_stop|
qty_btc        = risk_usdt / stop_distance
notional_usdt  = qty_btc * P_entry
eff_leverage   = notional_usdt / E
```

Guards applied in order:
1. `qty_btc = floor_to_step(qty_btc, LOT_SIZE_stepSize)`
2. `qty_btc >= MIN_QTY` else skip
3. `notional_usdt >= MIN_NOTIONAL` else skip
4. `eff_leverage <= regime_leverage_cap` else scale `qty_btc` down
5. Recompute `risk_usdt` after rounding; if actual risk > `1.1 * target`, drop one lot step.

Spot equivalent replaces `qty_btc = risk_usdt / stop_distance` with
`qty_btc = min(risk_usdt / stop_distance, cash_available / P_entry)`
and skips the leverage clamp.

---

## L. Capital Allocation Model

- **Cash bucket**: USDT wallet balance, refreshed every 30s.
- **Reserved margin**: for the open position only. Bot never
  pre-allocates margin for hypothetical future trades.
- **Idle reserve**: minimum 20% of equity in USDT, untouched, as a
  liquidation buffer.
- **Correlation handling**: BTCUSDT only for phase 1 — no correlation
  problem. If ETH/USDT is added later, the sizer will apply a
  correlation-adjusted cap: sum of BTC and ETH exposures capped at
  1.4× a single-instrument max.
- **When to stop for the day**: daily loss cap hit, or +3% realized
  gain hit (lock the day in). "Lock the day in" is optional but on by
  default; it prevents giving back a good session to a bad hour.
- **Overtrading guard**: max 8 trades per UTC day. Any 9th trade is
  refused with an alert.

---

## M. Bot Architecture

```
                       ┌───────────────────────────────┐
                       │            main.py            │
                       │  event loop + supervisor      │
                       └────────────┬──────────────────┘
                                    │
        ┌───────────────────────────┼────────────────────────────┐
        │                           │                            │
┌───────▼────────┐        ┌─────────▼──────────┐        ┌────────▼────────┐
│  Market Data   │        │   Signal Engine    │        │    Risk Engine  │
│  (WS + REST)   │───────▶│  (Regime + 3 engs) │───────▶│ (limits, sizer) │
└───────┬────────┘        └─────────┬──────────┘        └────────┬────────┘
        │                           │                            │
        │                           ▼                            ▼
        │                  ┌────────────────┐         ┌────────────────────┐
        │                  │ Filters (F.1-  │         │  Position Sizer +  │
        │                  │  F.10)          │        │    Kill-switch     │
        │                  └────────────────┘         └────────┬───────────┘
        │                                                       │
        │                                                       ▼
        │                                             ┌──────────────────┐
        │                                             │  Order Manager   │
        │                                             │ (REST, retries)  │
        │                                             └────────┬─────────┘
        │                                                      │
        │                                                      ▼
        │                                             ┌──────────────────┐
        │                                             │ State Manager +  │
        │                                             │  Exit Watcher    │
        │                                             └────────┬─────────┘
        │                                                      │
        ▼                                                      ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Storage: SQLite journal (trades, orders, fills, equity, events)       │
│  Logging: JSON structured logs, rotated                                │
│  Alerts: Telegram + optional email                                     │
└────────────────────────────────────────────────────────────────────────┘
```

### M.1 Modules

- `exchange/binance_rest.py` — signed REST client. Handles auth,
  rate-limit backoff, retries on 418/429/5xx, idempotency keys.
- `exchange/binance_ws.py` — async WebSocket. Subscribes to
  `btcusdt@kline_1m`, `btcusdt@kline_5m`, `btcusdt@kline_15m`,
  `btcusdt@kline_1h`, `btcusdt@bookTicker`, `btcusdt@aggTrade`,
  `btcusdt@markPrice`. Auto-reconnect with resumable state.
- `exchange/rate_limiter.py` — leaky-bucket by weight and by orders.
- `data/market_data.py` — rolling OHLCV buffers per timeframe.
- `data/orderbook.py` — top-N depth snapshot for filters F.1–F.2.
- `indicators/` — ATR, EMA, RSI, ADX, BB width, percentile, session tag.
- `strategy/regime.py` — regime router (E.4).
- `strategy/momentum.py`, `pullback.py`, `expansion.py` — three engines.
- `strategy/filters.py` — F.1–F.10 as pure functions.
- `risk/risk_engine.py` — J.1–J.7 caps.
- `risk/position_sizer.py` — K.
- `risk/kill_switch.py` — J.7 + T triggers.
- `execution/order_manager.py` — idempotent order placement, OCO emulation.
- `execution/exit_manager.py` — I.1–I.8.
- `execution/state_manager.py` — position + open orders state, reconciled every 30s vs REST.
- `backtest/engine.py` — event-driven backtester on 1m/5m candles.
- `backtest/metrics.py` — Q metrics.
- `storage/journal.py` — SQLite journal per N.
- `utils/logger.py` — structured JSON logs.
- `utils/alerts.py` — Telegram sink.

### M.2 Runtime modes

- `BACKTEST` — replays historical data through the same signal & risk pipeline.
- `PAPER` — live data, simulated fills at `bookTicker` +/- assumed slippage.
- `LIVE` — real orders on Binance. Requires a fresh 14-day paper run to pass Section S gates.

### M.3 Reliability

- WebSocket reconnect: exponential backoff (1s → 30s cap), resync
  klines via REST after reconnect, replay any missed bars into the
  strategy so state is deterministic post-reconnect.
- Order idempotency: bot generates `newClientOrderId` from a UUID and
  never re-uses it. Retries on 5xx use the same client order id so
  Binance dedupes.
- State reconciliation: every 30s, bot fetches `openOrders` and
  `positionRisk` from REST; any drift from local state = emergency
  reconcile (cancel unknowns, log, alert).
- Duplicate order protection: order manager refuses to place a new
  entry while any entry-side order for the symbol is `NEW`/`PARTIALLY_FILLED`.

### M.4 Security

- API keys in a `.env` file with `chmod 600`, loaded via `python-dotenv`.
  Never printed in logs. Bot refuses to start if key has withdraw
  permission enabled (Binance `getAccountInfo` returns permissions).
- IP-whitelist the exchange API key.
- Bot binary and config live outside the git repo on the VPS.
- Optional: use Binance's dedicated futures sub-account so the bot's
  blast radius is capped to that sub-account's balance.

---

## N. Database Schema

SQLite (single-writer, easy to inspect, easy to ship). All timestamps
are UTC ms since epoch.

```sql
CREATE TABLE IF NOT EXISTS equity_snapshots (
    ts             INTEGER PRIMARY KEY,        -- UTC ms
    wallet_usdt    REAL NOT NULL,
    equity_usdt    REAL NOT NULL,              -- wallet + unrealized
    unrealized_pnl REAL NOT NULL,
    mode           TEXT NOT NULL               -- BACKTEST|PAPER|LIVE
);

CREATE TABLE IF NOT EXISTS signals (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             INTEGER NOT NULL,
    engine         TEXT NOT NULL,              -- momentum|pullback|expansion
    side           TEXT NOT NULL,              -- LONG|SHORT
    entry_ref      REAL NOT NULL,
    stop_ref       REAL NOT NULL,
    tp1_ref        REAL NOT NULL,
    tp2_ref        REAL,
    score          REAL NOT NULL,
    regime_snap    TEXT NOT NULL,              -- JSON blob
    filter_results TEXT NOT NULL,              -- JSON blob of F.1-F.10
    accepted       INTEGER NOT NULL            -- 0/1
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
    exit_reason    TEXT,                       -- STOP|TP1|TP2|TIME|EMERG|OPPOSITE|VOL_COLLAPSE
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
    status         TEXT NOT NULL,              -- NEW|PARTIAL|FILLED|CANCELED|EXPIRED|REJECTED
    reduce_only    INTEGER NOT NULL,
    role           TEXT NOT NULL               -- ENTRY|STOP|TP1|TP2|TRAIL|EMERG
);

CREATE TABLE IF NOT EXISTS fills (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             INTEGER NOT NULL,
    client_id      TEXT REFERENCES orders(client_id),
    price          REAL NOT NULL,
    qty            REAL NOT NULL,
    fee_usdt       REAL NOT NULL,
    liquidity      TEXT NOT NULL               -- MAKER|TAKER
);

CREATE TABLE IF NOT EXISTS events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             INTEGER NOT NULL,
    level          TEXT NOT NULL,              -- INFO|WARN|ERROR|CRIT
    category       TEXT NOT NULL,              -- WS|REST|RISK|EXIT|KILL|RECONCILE
    message        TEXT NOT NULL,
    payload        TEXT
);

CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals(ts);
CREATE INDEX IF NOT EXISTS idx_trades_open_ts ON trades(open_ts);
CREATE INDEX IF NOT EXISTS idx_orders_trade  ON orders(trade_id);
CREATE INDEX IF NOT EXISTS idx_events_ts     ON events(ts);
```

---

## O. Pseudocode

```
loop_forever:
    on ws_message:
        market_data.update(msg)
    on bar_close(5m):
        # Only evaluate at completed bars.
        snap = market_data.snapshot()
        regime = regime_router.classify(snap)
        if regime.chop or not regime.tradeable(now_utc):
            log("regime=chop, sleeping")
            continue

        engine = pick_engine(regime)
        candidate = engine.evaluate(snap)   # or None
        if candidate is None:
            continue

        # Filters
        fr = run_all_filters(candidate, snap)
        journal.record_signal(candidate, regime, fr, accepted=fr.all_ok)
        if not fr.all_ok:
            continue

        # Risk gate
        if not risk.allow_new_trade(now_utc, state):
            continue

        # Sizing
        r = risk.effective_risk_pct(candidate.score, regime.score)
        qty = sizer.size(equity, candidate.entry_ref, candidate.stop_ref, r,
                         regime_leverage_cap)
        if qty is None:
            continue

        trade = state.begin_trade(candidate, qty, r)
        order_manager.enter(trade)

    on order_update(ord):
        state.apply(ord)
        exit_manager.on_order_update(ord)

    on tick(1m):
        exit_manager.check_time_and_vol_exits(state.open_trade)
        risk.check_daily_and_dd_caps()
        if risk.kill():
            emergency.flatten_all()
```

---

## P. Python Implementation Plan

- **Language**: Python 3.11+.
- **Async model**: `asyncio` throughout. One event loop.
- **Deps**:
  - `aiohttp` for REST.
  - `websockets` for market data feeds.
  - `orjson` for JSON hot path.
  - `numpy` + `pandas` for indicators + backtest.
  - `pydantic` for config models.
  - `sqlite3` (stdlib) via `aiosqlite` for journal.
  - `structlog` for JSON logs.
  - `pytest` + `pytest-asyncio` for tests.
- **Config**: `config/config.yaml` + `.env` for secrets. Pydantic validates.
- **Layout**: see Section M and the repo tree in `src/`.
- **Concurrency guards**:
  - A single asyncio Lock protects the "one open trade" invariant.
  - Order manager uses per-symbol idempotency keys.
- **Deterministic time**: bot only makes decisions at bar-close events
  timestamped by the exchange, never `time.time()`. This keeps
  backtest and live semantically identical.

---

## Q. Backtesting Plan

### Q.1 Data
- 1-minute BTCUSDT klines from Binance REST `/fapi/v1/klines`, at
  least 3 years, saved as parquet in `data/`.
- Funding rate history from `/fapi/v1/fundingRate`.
- Optional: aggregate trade history for taker-buy ratio validation.

### Q.2 Method
- Event-driven replay: for each 1m bar, emit the bar to the strategy;
  every 5th bar, emit a 5m bar-close event; every 15th, a 15m; every
  60th, a 1h. This mirrors live event flow.
- **No lookahead**: indicators computed from *closed* bars only.
- Slippage model: `entry_price = signal_price + spread/2 + k * atr%`,
  `k = 0.15` for markets, `0.0` for stops (filled at stop level with
  1 tick slip).
- Fee model: taker 0.0450%, maker 0.018% (with BNB discount).
- Funding: apply at 00:00/08:00/16:00 UTC if position open.

### Q.3 Metrics reported
- Total return, CAGR, max drawdown, longest DD duration.
- Profit factor, expectancy in R.
- Win rate, avg win / avg loss ratio, R distribution histogram.
- Sharpe (daily), Sortino (daily).
- MAE / MFE per trade.
- Turnover, fee drag, funding drag.
- Trades per day, session breakdown.

### Q.4 Walk-forward
- 6-month in-sample → 2-month out-of-sample, rolled 6 times over 4 years.
- OOS profit factor ≥ 1.3 required in ≥ 4 of 6 windows.

### Q.5 Monte Carlo drawdown
- Shuffle trade order 5,000 times, compute worst DD distribution.
- Report 95th percentile DD; go-live cap = 1.5× median historical DD.

### Q.6 Slippage stress
- Re-run with slippage 2× and 3× normal. Strategy must remain profit
  factor ≥ 1.2 at 2× and ≥ 1.0 at 3×.

---

## R. Paper Trading Plan

- **Duration**: minimum **14 consecutive calendar days**.
- **Data**: live WebSocket, simulated fills at `bookTicker` mid ± modelled slippage.
- **Behavior gates** to pass before Live:
  - Realized/theoretical fill delta ≤ 0.05% average.
  - Signal count within ±20% of backtest expectation for the same window.
  - Zero uncaught exceptions.
  - WebSocket reconnected without missing bars at least once.
  - Kill-switch dry-run test executed and clean.
  - Match on the trade journal between paper and backtest for the same window (≥ 85% signal identity).

---

## S. Live Deployment Rules

1. Deploy on a VPS in `ap-northeast-1` (Tokyo) or `ap-southeast-1`
   (Singapore) — closest to Binance's primary infra.
2. Start with **10% of intended capital** for the first 14 live days.
   Bot logs a WARN if operator tries to raise capital before then.
3. First live position size cap: **0.4% per trade** regardless of
   config. Ramps to configured base only after the 14-day pilot passes
   with drawdown ≤ 3% and profit factor ≥ 1.2.
4. Operator must have Telegram alerts on. Bot page-out categories:
   `KILL`, `EMERGENCY_EXIT`, `RECONCILE_MISMATCH`, `API_ERROR_RATE`,
   `DAILY_LOSS_CAP`, `WEEKLY_LOSS_CAP`.
5. Weekly review is mandatory: operator reads the last 7 days of
   `events` + `trades` and signs off in a `run_log.md`. If a review
   is missed, bot auto-pauses at the next UTC midnight.
6. Any config change requires a git commit + a paper run of ≥ 48h.
   Bot refuses to start if `config.yaml`'s git hash isn't the same as
   the paper-log config hash (verified via a `config_hash` in the
   events table).

---

## T. Failure Scenarios & Protection

| Scenario                                | Protection                                                                          |
|-----------------------------------------|-------------------------------------------------------------------------------------|
| WebSocket dies                          | Auto-reconnect, resync from REST, replay missed bars. If gap > 5 bars → flat.       |
| REST 5xx storm                          | Exponential backoff. If error rate > 10% for 60s while position open → emergency.   |
| Rate limit ban (418)                    | Freeze all new orders, keep exits alive via alternative order channel, alert.       |
| Partial fill on entry                   | If unfilled qty < 20% after 3s: cancel and use filled size only.                    |
| Partial fill on stop / TP               | Loop: keep firing reduce-only market until `positionAmt == 0`.                      |
| Exchange margin insufficient (-2019)    | Cancel entry, recompute equity, alert. Do not retry same size.                      |
| Price protection (-4131)                | Retry with reduced qty and 2 ticks off; if still failing → emergency reduce-only.   |
| Liquidation approach                    | If mark price within 25% of liquidation distance → market-flatten immediately.      |
| Funding spike                           | Skip new entries 5 min before funding when funding × direction < −0.05%.            |
| Exchange maintenance window             | Scheduled window in config; bot flattens 10 minutes before, does not enter during.  |
| Clock drift                             | NTP sync on host; bot rejects timestamps from exchange > 250ms off local.           |
| Key compromise                          | Withdraw permission disabled at key level; IP whitelist; kill-switch by revoking.   |
| Local process crash                     | systemd `Restart=always`, state rebuilt from journal + REST reconciliation on boot. |
| Bug in new deploy                       | 48h paper gate + config-hash pinning prevent bad config reaching live.              |

---

## U. Final Recommendation

- Trade **BTCUSDT USDⓈ-M perpetual futures**, isolated margin, 5×
  effective leverage cap.
- Deploy the three-engine hybrid (Momentum / Pullback / Expansion) with
  the regime router and the F.1–F.10 filter stack. This is aggressive
  because it takes both sides, sizes into strong regime scores, and
  accepts high turnover; it is controlled because every signal has an
  ATR-scaled stop, a hard daily / weekly / drawdown cap, and a
  fail-safe kill-switch with structural emergency market exits.
- Do **not** enable live trading until:
  - Backtest walk-forward passes (Q.4).
  - Monte Carlo 95th DD < 2 × configured drawdown cap (Q.5).
  - Paper 14-day trial passes (R).
  - Live pilot at 10% capital + 0.4% risk-per-trade passes 14 days (S).
- Realistic expectation, given the fee/funding drag on BTC intraday
  and the strategy's design: profit factor 1.3–1.7 in favorable
  regimes, 15–25% annualized *if* it holds up out of sample, with
  routine 8–12% drawdowns and occasional 15% drawdowns. **Any
  advertised expectation above that is a lie.** Losing months will
  happen. What the bot must guarantee is *survival* through them.
