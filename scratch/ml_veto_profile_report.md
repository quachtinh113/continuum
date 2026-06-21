# ML Gatekeeper Veto Counterfactual Profiling Report

Analyzed trades under the optimized Break-Even settings (Activation: 1.25 ATR, Buffer: -0.05 ATR).

## Overall Performance Comparison

| Metric | WITH ML Veto (Baseline) | WITHOUT ML Veto (Counterfactual) | Difference |
| :--- | :--- | :--- | :--- |
| **Net Profit** | $397.29 (3.97%) | $-1586.43 (-15.86%) | $+1983.72 |
| **Win Rate** | 55.13% | 54.21% | +0.92% |
| **Profit Factor** | 1.42 | 0.80 | +0.62 |
| **Max Drawdown** | 3.46% | 21.89% | -18.43% |
| **Total Trades** | 156 | 594 | -438 |

## ML Veto Efficacy Analysis
* **Total Vetoed Trades:** 63
* **Saved Losses:** 15 trades (Veto avoided a larger loss)
* **Killed Wins:** 8 trades (Veto accidentally cut a winning trade)
* **Net Financial Impact of ML Gatekeeper:** **$+1983.72 USD**

### Vetoed Trades Breakdown Table

| Symbol | Entry_Time | Veto_PnL | CF_PnL | CF_Outcome | Impact |
| --- | --- | --- | --- | --- | --- |
| EURUSD | 2025-12-15 15:00 | $-3.78 | $-21.96 | FORCE_CLOSE_RR_LIMIT | $+18.18 |
| GBPUSD | 2025-12-19 20:00 | $2.66 | $12.49 | TAKE_PROFIT | $-9.83 |
| GBPUSD | 2025-12-23 09:00 | $-1.52 | $-30.09 | FORCE_CLOSE_RR_LIMIT | $+28.57 |
| EURUSD | 2025-12-24 01:00 | $0.20 | $-20.10 | 12H_CUT_ALL | $+20.30 |
| EURUSD | 2025-12-31 09:00 | $-8.20 | $-24.35 | FORCE_CLOSE_RR_LIMIT | $+16.15 |
| GBPUSD | 2025-12-31 09:00 | $-16.08 | $-27.69 | FORCE_CLOSE_RR_LIMIT | $+11.61 |
| EURUSD | 2026-01-15 14:00 | $-7.60 | $-15.00 | 12H_CUT_ALL | $+7.40 |
| GBPUSD | 2026-01-15 18:00 | $4.62 | $-0.42 | BREAK_EVEN | $+5.04 |
| EURUSD | 2026-01-20 17:00 | $-8.04 | $-18.13 | FORCE_CLOSE_RR_LIMIT | $+10.09 |
| GBPUSD | 2026-01-22 19:00 | $-4.45 | $11.86 | TAKE_PROFIT | $-16.31 |
| EURUSD | 2026-01-22 19:00 | $-7.44 | $-0.43 | BREAK_EVEN | $-7.01 |
| EURUSD | 2026-01-27 19:00 | $25.95 | $20.19 | TAKE_PROFIT | $+5.76 |
| EURUSD | 2026-01-29 00:00 | $-11.24 | $-28.16 | FORCE_CLOSE_RR_LIMIT | $+16.92 |
| EURUSD | 2026-03-12 14:00 | $3.24 | $9.78 | TAKE_PROFIT | $-6.54 |
| EURUSD | 2026-03-19 21:00 | $-9.58 | $-15.36 | FORCE_CLOSE_RR_LIMIT | $+5.78 |
| GBPUSD | 2026-03-23 08:00 | $8.20 | $-30.64 | FORCE_CLOSE_RR_LIMIT | $+38.84 |
| EURUSD | 2026-03-26 20:00 | $-1.25 | $13.08 | TAKE_PROFIT | $-14.34 |
| EURUSD | 2026-04-09 19:00 | $1.05 | $10.42 | TAKE_PROFIT | $-9.37 |
| EURUSD | 2026-04-14 11:00 | $1.26 | $11.02 | TAKE_PROFIT | $-9.76 |
| GBPUSD | 2026-04-17 13:00 | $-16.14 | $-25.04 | FORCE_CLOSE_RR_LIMIT | $+8.90 |
| EURUSD | 2026-05-13 09:00 | $-7.20 | $12.25 | TAKE_PROFIT | $-19.45 |
| EURUSD | 2026-06-03 13:00 | $-7.90 | $-16.38 | 12H_CUT_ALL | $+8.48 |
| GBPUSD | 2026-06-08 15:00 | $2.22 | $-11.12 | FORCE_CLOSE_RR_LIMIT | $+13.34 |
