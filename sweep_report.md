# Parameter Sweep Optimization Report

This report displays the performance across 4 core symbols (EURUSD, GBPUSD, USDJPY, XAUUSD) over 6 months.

## Matrix Results Table

| Run | Entry_Th | TP_Mult | DCA_Steps | Profit_USD | Profit_Pct | Trades | Win_Rate | Profit_Factor | Max_DD_Pct | BE_Exits | Veto_Exits | TP_Exits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.85 | 1.5 | (2.0, 3.0, 4.0) | -612.08 | -6.12 | 1000 | 37.9 | 0.83 | 8.46 | 160 | 708 | 107 |
| 2 | 0.35 | 1.5 | (2.0, 3.0, 4.0) | 103.54 | 1.04 | 176 | 32.39 | 1.16 | 1.61 | 74 | 50 | 43 |
| 3 | 0.55 | 1.5 | (2.0, 3.0, 4.0) | 15.02 | 0.15 | 366 | 31.97 | 1.01 | 3.35 | 121 | 141 | 86 |
| 4 | 0.55 | 2.0 | (2.0, 3.0, 4.0) | 28.31 | 0.28 | 324 | 37.65 | 1.01 | 6.35 | 66 | 172 | 75 |
| 5 | 0.55 | 1.5 | (1.5, 2.5, 3.5) | -21.11 | -0.21 | 367 | 31.61 | 0.99 | 4.22 | 122 | 141 | 85 |
| 6 | 0.55 | 1.5 | (2.5, 3.5, 4.5) | -4.26 | -0.04 | 366 | 32.24 | 1.0 | 3.37 | 121 | 134 | 86 |

## Recommendations
- **Best Performing Safe Run (Max DD < 6%):** Run 2
  - **ML Entry Safe Threshold:** 0.35
  - **Take Profit ATR Multiplier:** 1.5
  - **DCA Spacing Steps:** (2.0, 3.0, 4.0)
  - **Net Profit:** $103.54 (1.04%)
  - **Max Drawdown:** 1.61%
  - **Total Trades:** 176
  - **Win Rate:** 32.39%
