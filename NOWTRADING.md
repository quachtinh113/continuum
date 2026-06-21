# MISSION OBJECTIVE
You are an expert Principal Quantitative Engineer and Core Systems Architect. Your task is to fully implement "V9 Continuum" — an institutional-grade, hybrid quantitative trading system built with Python 3.13. 

# ARCHITECTURE PRINCIPLE: HYBRID PORTFOLIO CONTROL
The system MUST decouple alpha generation from portfolio risk management. It operates as an ecosystem of Independent Signal Engines (per symbol) constrained under a single, supreme Centralized Portfolio Risk Governor.

# PROJECT REPOSITORY STRUCTURE
Initialize and implement the project following this precise modular directory:
v9_continuum/
├── core/
│   └── governor.py          # Centralized Portfolio Risk Governor (State & Risk manager)
├── layers/
│   ├── regime.py            # Market environment detection (OU Process, HMM, KAMA)
│   ├── signal.py            # Symbol-specific Signal Engines (SMC, LightGBM, ADX)
│   ├── position.py          # Capital allocation and cashflow sizing
│   └── execution.py         # Order routing, session time filters, slippage/spread protection
├── config/
│   └── portfolio_matrix.json # Global risk limits and macroeconomic asset configuration
└── main.py                  # System entry point and event-loop initialization

# SPECIFICATIONS BY LAYER

## 1. CONFIGURATION (config/portfolio_matrix.json)
Define a JSON structure enforcing:
- max_open_positions: 3
- max_total_risk_percent: 2.0
- max_daily_drawdown_percent: 3.0
- max_usd_exposure: 2
- max_gold_index_combo: 1
- news_lock_minutes: 30

## 2. MARKET REGIME LAYER (layers/regime.py)
Implement mathematical models for structural detection:
- Asia Session: Use the Ornstein-Uhlenbeck process to calculate mean-reversion speed (\theta) and long-term mean (\mu). Combine with a Kalman Filter to track real-time price state and Z-score.
- Europe Session: Implement a Hidden Markov Model (HMM) to detect state transitions (Liquidity Accumulation vs. Price Expansion).
- US Session: Implement Kaufman's Adaptive Moving Average (KAMA) with Dynamic ADX to track pure momentum.

## 3. SIGNAL ENGINE & CORRELATION LAYER (layers/signal.py & core/governor.py)
- Each symbol runs its own independent logic setup (e.g., SMC Liquidity Grab for EURUSD, KAMA trend-following for US30).
- CENTRAL GOVERNOR CONCURRENCY RULE: If highly correlated assets (e.g., EURUSD and GBPUSD) fire identical entry signals simultaneously, the Central Governor must intercept them in an async queue (100-200ms window), score them based on (ADX * 0.7) - (Spread * 0.3), and only allow the single best asset to route to Execution.

## 4. CENTRAL RISK GOVERNOR RULES (core/governor.py)
The Governor must monitor global system state continuously:
- If net exposure on any factor (like USD) or asset combo (Gold + Index) is breached, deny further entries.
- If current equity drawdown >= max_daily_drawdown_percent, trigger a *Global Kill Switch*: send emergency market close orders for all open positions, wipe pending orders, and set system_status = "LOCKED".
- Macro News Filter: Read timestamps of High Impact news. Freeze order routing (Blackout Window) from T-30 mins to T+15 mins. Post-news, unlock only when real-time ATR co-hẹp dynamically approaches baseline levels (Exponential Volatility Decay Engine).

## 5. POSITION & EXECUTION LAYER (layers/position.py & layers/execution.py)
- Position sizing must dynamically adjust based on account equity, ATR-based stop distance, and risk parameters.
- Execution must handle execution windows per session and prevent order routing if current_spread > max_allowed_spread. Create mock broker API wrappers for testing.

# ANTIGRAVITY WORKFLOW REQUIREMENTS
1. *Plan First*: Generate a comprehensive "Implementation Plan" and "Task List" as your initial Antigravity Artifacts. Wait for my confirmation or adjustments if necessary, then proceed.
2. *Modular Code*: Write clean, production-grade, type-hinted Python 3.13 code. Use vectorization (NumPy/Pandas/Polars) where performance is critical.
3. *Robust Safety*: Ensure edge cases (API disconnects, unexpected data formats, out-of-bounds calculations) are guarded with clean exception handling and logging.
4. *Verification*: Write standard pytest unit tests for core/governor.py to verify the execution of the Global Kill Switch and correlation scoring rules under mock stress test scenarios.

Let's begin. Initialize the repository and present your execution plan.