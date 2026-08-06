# ML Gatekeeper Veto Counterfactual Profiling Report

Analyzed trades under the optimized Break-Even settings (Activation: 1.25 ATR, Buffer: -0.05 ATR).

## Overall Performance Comparison

| Metric | WITH ML Veto (Baseline) | WITHOUT ML Veto (Counterfactual) | Difference |
| :--- | :--- | :--- | :--- |
| **Net Profit** | $-3229.65 (-32.30%) | $-3229.65 (-32.30%) | $+0.00 |
| **Win Rate** | 9.45% | 9.45% | +0.00% |
| **Profit Factor** | 0.43 | 0.43 | +0.00 |
| **Max Drawdown** | 34.89% | 34.89% | +0.00% |
| **Total Trades** | 1069 | 1069 | 0 |

## ML Veto Efficacy Analysis
* **Total Vetoed Trades:** 0
* **Saved Losses:** 0 trades (Veto avoided a larger loss)
* **Killed Wins:** 0 trades (Veto accidentally cut a winning trade)
* **Net Financial Impact of ML Gatekeeper:** **$+0.00 USD**

No trades were vetoed by the ML gatekeeper in this run.
