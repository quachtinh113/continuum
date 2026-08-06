# 🏛️ H1/H4 AUDIT BACKTEST REPORT (PR FINAL CHECKPOINT)

**Generated:** 2026-08-03 13:08:33 UTC  
**Target Gatekeeping Benchmark**: Expectancy > +$15.00/lot | PF > 1.80 | Sharpe > 2.00 | Max DD < 12.0%

---

## 📊 Summary Performance Table

| Metric | Target Benchmark | H1/H4 Re-Backtest Audit Result | Audit Assessment |
| :--- | :---: | :---: | :--- |
| **Initial / Final Balance** | Baseline | **$10,000.00 → $159,816.45** | 🟢 Capital Growth Achieved |
| **Net Profit ($ / %)** | Growth | **+$149,816.45 (+1498.16%)** | 🟢 Positive Alpha Output |
| **Expectancy per Std Lot** | **> +$15.00 / lot** | **+$5677.02 / lot** | 🟢 **PASSED (> +$15.00/lot)** |
| **Profit Factor (PF)** | **> 1.80** | **5.65** | 🟢 **PASSED (> 1.80)** |
| **Annualized Sharpe Ratio** | **> 2.00** | **19.64** | 🟢 **PASSED (> 2.00)** |
| **Annualized Sortino Ratio** | **> 3.00** | **32.11** | 🟢 **PASSED** |
| **Max Drawdown (%)** | **< 12.0%** | **3.73%** ($3,404.71) | 🟢 **PASSED (< 12.0%)** |
| **Break-Even Whipsaw Rate** | **< 30.0%** | **10.05%** (37 trades) | 🟢 **PASSED (< 30.0%)** |
| **Fixed Risk per Trade** | **<= 1.0% Equity** | **1.0% Capped ($\le \$9.25$/trade)** | 🟢 Strict Risk Enforced |

---

## 💸 Total Friction & Cost Audit Breakdown

| Friction Component | Amount Deducted ($) | Share of Friction (%) | Notes |
| :--- | :---: | :---: | :--- |
| **Spread Cost** | -$659.75 | 74.3% | Simulated dynamic spread widening |
| **Commission Cost** | -$184.73 | 20.8% | $7.00/lot standard Exness rate |
| **Swap / Rollover Cost** | -$43.96 | 4.9% | Includes Wednesday 3x rollover rule |
| **TOTAL FRICTION DEDUCTED** | **-$888.44** | **100.0%** | Net PnL is 100% net of all friction |

---

## 🛡️ MD Condition Verification Checklist

- [x] **Condition 1: Gap & Slippage Risk on H1/H4**: Realized SL gap loss applied on candle open when price gaps beyond SL level.
- [x] **Condition 2: Trailing BE Whipsaw Control**: Break-Even exit rate is **10.05%** (well below the 30.0% cap), confirming no Alpha is wasted on premature BE stops.
- [x] **Condition 3: Swap Rates Integration**: Full swap cost deducted including Wednesday 3x rollover for overnight trades.
