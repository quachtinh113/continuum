# Scenario C Parameter Sweep Optimization Report

Generated: 2026-06-15 21:56:54 Local

We evaluated 60 parameter configurations over historical M15 data from EURUSD, GBPUSD, XAUUSD, and BTCUSD between Jan 2026 and Jun 2026. Initial balance was set to **$1,015.23** with variable spread penalty and daily stop limit checks activated.

## Top 10 Configurations (Sorted by Net Profit, minimized hard daily stop violations)

| Rank | ML Entry Th | TP Mult | DCA Spacing | Net Profit ($) | Profit (%) | Win Rate (%) | Profit Factor | Max Drawdown (%) | Daily Violations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.45 | 2.0 | (1.5, 2.0, 2.5) | $443.33 | 43.67% | 45.16% | 1.47 | 16.09% | 0 |
| 2 | 0.45 | 2.5 | (1.5, 2.0, 2.5) | $250.07 | 24.63% | 42.21% | 1.24 | 19.70% | 0 |
| 3 | 0.45 | 2.0 | (2.0, 3.0, 4.0) | $223.00 | 21.97% | 45.62% | 1.24 | 21.91% | 0 |
| 4 | 0.45 | 2.5 | (2.0, 3.0, 4.0) | $210.43 | 20.73% | 41.31% | 1.21 | 21.39% | 0 |
| 5 | 0.45 | 2.0 | (1.0, 1.5, 2.0) | $201.64 | 19.86% | 48.23% | 1.17 | 26.49% | 0 |
| 6 | 0.45 | 2.5 | (1.0, 1.5, 2.0) | $156.49 | 15.41% | 44.03% | 1.12 | 29.20% | 0 |


## Recommendations
The best configuration found is **Rank 1**:
- **ML Entry Safe Threshold:** `0.45`
- **Take Profit ATR Multiplier:** `2.0`
- **DCA Spacing Steps:** `(1.5, 2.0, 2.5)`
- **Expected Net Profit:** `$443.33`
- **Win Rate:** `45.16%`
- **Profit Factor:** `1.47`
- **Max Drawdown:** `16.09%`
- **Daily Hard Stop Violations:** `0` days
