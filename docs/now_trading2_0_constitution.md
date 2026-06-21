Q Tỉnh, nếu mục tiêu là dùng làm **Constitution gốc cho Quant V9 / NowTrading Quant Core**, mình sẽ thiết kế lại theo hướng:

* Đủ đơn giản để audit
* Đủ chặt để production 24/5
* Không lặp lại lỗi Signal Starvation
* Không lặp lại lỗi Data Starvation
* Không lặp lại lỗi ML Gatekeeper
* Phù hợp O Systems – NowTrading – Human In The Loop

# NOWTRADING 2.1.1 CONSTITUTION

## Official Strategy Constitution for Quant V9

Version: 2.1.1
Status: ACTIVE
Authority: Q Tỉnh

---

# 1. Core Philosophy

NowTrading means:

Observe → Validate → Execute → Audit

The system never predicts.

The system reacts only to valid market conditions.

Human remains the final decision maker.

Risk Engine retains technical veto power.

---

# 2. Supported Markets

Forex:

* EURUSD
* GBPUSD
* USDJPY
* USDCHF
* AUDUSD
* NZDUSD
* USDCAD

Indices:

* US30
* US100
* US500

Metals:

* XAUUSD

Crypto:

* BTCUSD

---

# 3. Mandatory Timeframes

Required:

* H4
* H1
* M15

No trade is valid if any timeframe is missing.

---

# 4. Market Regime Engine

ADX defines regime.

ADX < 18

* RANGE

18 <= ADX < 25

* TRANSITION

ADX >= 25

* TREND

Rules:

RANGE

* Mean Reversion only
* Reduced risk

TRANSITION

* No new entries
* Manage existing positions only

TREND

* Full strategy enabled

---

# 5. BUY Constitution

Trend Filter:

RSI_H4 > 55

AND

RSI_H1 > 55

Entry Trigger:

RSI_M15 > 50

AND

M15 momentum aligned with H1/H4

AND

Pullback exhaustion confirmed

Signal:

BUY

---

# 6. SELL Constitution

Trend Filter:

RSI_H4 < 45

AND

RSI_H1 < 45

Entry Trigger:

RSI_M15 < 50

AND

M15 momentum aligned with H1/H4

AND

Pullback exhaustion confirmed

Signal:

SELL

---

# 7. Pullback Exhaustion Confirmation

BUY:

* RSI_M15 rising
* Current close > previous close
* No fresh local low

SELL:

* RSI_M15 falling
* Current close < previous close
* No fresh local high

Without confirmation:

NO TRADE

---

# 8. Hourly Entry Gate

Evaluation occurs every hour.

Rules:

* One trade cycle per symbol per hour
* No duplicate trade within hourly bucket
* No trade during first 60 seconds of new hour

Emergency Event Mode:

Allowed for:

* CPI
* NFP
* FOMC

Requires explicit enable flag.

---

# 9. Trade Cycle Management

Each cycle stores:

* symbol
* direction
* session
* entry_time
* entry_price
* dca_layers
* profit_usd
* holding_hours

---

# 10. Profit Management

If:

holding_time > 1 hour

AND

profit > 5 USD

Action:

CLOSE CYCLE

---

# 11. 12-Hour Review Rule

If:

holding_time > 12 hours

AND

profit <= 0

Action:

Do not close positions immediately.

Activate ATR_ADAPTIVE_DCA_CHECK:
* If abs(current_price - average_entry_price) <= ATR_DCA_CHECK_MULTIPLIER * ATR: continue holding.
* If price is outside this normal ATR range: freeze DCA.
* Review trend using ADX:
  - If ADX > 25 (strong trend): reduce exposure (remove the worst performing DCA layer). If no DCA layers exist, cut all.
  - If ADX <= 25 (weak trend / range): cut all positions.

---

# 12. 24-Hour Rule

If:

holding_time > 24 hours

AND

profit <= 0

Action:

Do not force close all positions unconditionally.

Activate REGIME_FILTER_EXIT:
* Only close if trend reversed: ADX > 25 AND (for BUY: RSI_H4 < 45 and RSI_H1 < 45; for SELL: RSI_H4 > 55 and RSI_H1 > 55).
* OR close if H1 RSI is overextended against the position (RSI_H1 < 30 for BUY, RSI_H1 > 70 for SELL).
* Otherwise, if the market remains sideways, continue to hold positions.

---

# 13. ATR DCA Constitution

DCA only when original thesis remains valid.

Layer spacing:

Layer 1 = 1 ATR

Layer 2 = 1.5 ATR

Layer 3 = 2 ATR

Maximum:

3 layers

---

# 14. DCA Kill Conditions

Stop DCA immediately if:

* RSI_H4 reverses
* RSI_H1 reverses
* ADX collapses below regime threshold
* Risk Engine veto
* 12h review freezes DCA
* 24h rule activated

---

# 15. Risk Engine Constitution

Risk Engine has final technical authority.

Mandatory veto:

* Missing MTF data
* Missing RSI
* Missing ADX
* Missing ATR
* Data stale
* Spread too high
* Daily drawdown exceeded
* Symbol exposure exceeded
* Portfolio exposure exceeded
* Duplicate trade

Risk Engine cannot be bypassed.

---

# 16. Data Quality Constitution

Required:

Tick Age < 120 seconds

RSI_H4 valid

RSI_H1 valid

RSI_M15 valid

ADX valid

ATR valid

No NaN values

Failure:

NO TRADE

---

# 17. Portfolio Governance

Maximum correlated exposure allowed.

Examples:

EURUSD BUY
GBPUSD BUY
AUDUSD BUY

Count as USD short exposure.

Portfolio risk limits override symbol signals.

---

# 18. ML Governance

ML operates in OBSERVE ONLY mode.

ML may:

* score
* rank
* audit
* explain

ML may NOT:

* force trade
* veto trade
* modify thresholds
* modify risk rules

---

# 19. Fleet Governance

Fleet Status:

GREEN

* > 90% bots healthy

YELLOW

* 70%–90% healthy

RED

* <70% healthy

Rules:

RED state:

* block new entries
* allow exits only

---

# 20. Audit Constitution

Every decision must log:

* timestamp
* symbol
* session
* RSI_H4
* RSI_H1
* RSI_M15
* ADX
* ATR
* signal
* risk_decision
* execution_action
* reason

No log = invalid decision.

---

# 21. Audit Severity

INFO

Normal operation

WARNING

Missing data

CRITICAL

Risk violation

FATAL

Trade without audit trail

---

# 22. Unit Test Constitution

Required tests:

* BUY
* SELL
* HOLD
* Regime classification
* Hourly gate
* Pullback confirmation
* ATR DCA
* Risk veto
* Data stale
* Portfolio exposure
* Profit close
* 12h review
* 24h close

No deployment without passing tests.

---

# 23. Non-Negotiable Rules

AI may NOT:

* Force trade
* Fake tests
* Delete audit logs
* Bypass risk
* Trade live without approval
* Modify strategy thresholds
* Modify DCA rules
* Modify Constitution

---

# 24. Build Order

MTF Builder
→ Regime Engine
→ Signal Engine
→ Hourly Gate
→ Trade Cycle Manager
→ ATR DCA Engine
→ Risk Engine
→ Portfolio Engine
→ Audit Logger
→ Unit Tests

---

# 25. Final Authority

Human-in-the-loop.

Q Tỉnh is final trading authority.

Risk Engine retains technical veto.

All code changes must comply with this Constitution.

---

# 26. Resilience & Connection Governance (v2.1.1)

To prevent crash loops, data starvation, and system lockups:

* **Weekend Cooldown**: Markets close Friday 22:00 UTC and reopen Sunday 22:00 UTC. Bot detects this schedule and sleeps for 300 seconds (5 minutes) periodically, suppressing unnecessary checks.
* **Auto-Restart**: The bot startup loop automatically restarts the bot up to 50 times with a 30-second delay upon crash. Clean exit (code 0) terminates the loop.
* **MT5 Connector Reconnection**: If connection to MT5 terminal fails, the connector retries up to 3 times with progressive backoff (5s, 10s, 30s) before reporting failure.
* **Startup Data Sync Wait**: Bot pauses for 30 seconds on successful MT5 startup connection to allow the MT5 terminal to fully synchronize historical data and prevent stale/invalid rates errors.
* **Circuit Breaker**: If all symbols fail to get rates for 5 consecutive iterations, the bot trips the circuit breaker, disconnects, resets, and reconnects the MT5 connection to heal the terminal process.
* **Error Log Throttling**: Identical API/rate errors (e.g. Exness -1 Terminal Call failed) are throttled and only logged once every 300 seconds (5 minutes) per symbol/error key, preventing disk/log bloating.

Phiên bản này phù hợp hơn với Quant V9 / NowTrading hiện tại vì nó bổ sung các cơ chế phòng vệ tự động giúp bot chạy liên tục 24/5 không bị gián đoạn hay tràn ổ đĩa log khi gặp sự cố mạng hoặc MT5 terminal.
