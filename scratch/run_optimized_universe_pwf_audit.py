import os
import sys
import math
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import scipy.stats as stats

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from v9_continuum.backtest import V9ContinuumBacktester

def run_comparison_audit():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 95)
    print(" CONTINUUM V9: FOCUSED UNIVERSE (XAUUSD, USDJPY, AUDUSD, USDCAD) PURGED WALK-FORWARD AUDIT")
    print("=" * 95)

    focused_universe = ["XAUUSD", "USDJPY", "AUDUSD", "USDCAD"]
    initial_balance = 10000.0

    folds = [
        {"fold": 1, "test_start": datetime(2025, 10, 1, tzinfo=timezone.utc), "test_end": datetime(2025, 12, 1, tzinfo=timezone.utc)},
        {"fold": 2, "test_start": datetime(2025, 12, 1, tzinfo=timezone.utc), "test_end": datetime(2026, 2, 1, tzinfo=timezone.utc)},
        {"fold": 3, "test_start": datetime(2026, 2, 1, tzinfo=timezone.utc), "test_end": datetime(2026, 4, 1, tzinfo=timezone.utc)},
        {"fold": 4, "test_start": datetime(2026, 4, 1, tzinfo=timezone.utc), "test_end": datetime(2026, 6, 18, tzinfo=timezone.utc)},
    ]

    all_oos_trades = []
    print("\n[Phase 1] Executing Rolling Purged Walk-Forward on Focused Universe...")
    print("-" * 95)

    for f in folds:
        tester = V9ContinuumBacktester(risk_percent=0.5, ml_veto_threshold=0.80)
        port, _ = tester.run(focused_universe, f["test_start"], f["test_end"], initial_balance=initial_balance)
        trades = port.closed_cycles
        all_oos_trades.extend(trades)

        pnls = [t["final_pnl"] for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        net_pnl = sum(pnls)
        wr = (len(wins) / len(pnls) * 100.0) if pnls else 0.0
        pf = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else (99.0 if wins else 0.0)

        print(f"  Fold {f['fold']} [{f['test_start'].strftime('%Y-%m-%d')} to {f['test_end'].strftime('%Y-%m-%d')}]: "
              f"Trades: {len(trades):>3} | Win Rate: {wr:5.1f}% | Net PnL: ${net_pnl:+8.2f} | PF: {pf:4.2f} | Max DD: {port.max_drawdown_pct:4.2f}%")

    print("-" * 95)
    print(f"Total Out-of-Sample Trades (Focused Universe): {len(all_oos_trades)}\n")

    pnls = np.array([t["final_pnl"] for t in all_oos_trades])
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]

    total_trades = len(pnls)
    win_rate = (len(wins) / total_trades) * 100.0
    gross_profit = float(np.sum(wins))
    gross_loss = float(abs(np.sum(losses)))
    net_pnl = float(np.sum(pnls))
    return_pct = (net_pnl / initial_balance) * 100.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 99.0

    avg_win = float(np.mean(wins)) if len(wins) > 0 else 0.0
    avg_loss = float(abs(np.mean(losses))) if len(losses) > 0 else 0.0
    payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0

    # Max Consecutive Losses
    max_cons = 0
    curr_cons = 0
    for p in pnls:
        if p <= 0:
            curr_cons += 1
            max_cons = max(max_cons, curr_cons)
        else:
            curr_cons = 0

    # Portfolio Equity Curve & Drawdown
    equity_curve = initial_balance + np.cumsum(pnls)
    peaks = np.maximum.accumulate(equity_curve)
    drawdowns = (peaks - equity_curve) / peaks * 100.0
    max_dd_pct = float(np.max(drawdowns))
    max_dd_usd = float(np.max(peaks - equity_curve))

    # Annualized Sharpe & Sortino
    days = (folds[-1]["test_end"] - folds[0]["test_start"]).days
    years = max(0.1, days / 365.0)
    trades_per_year = total_trades / years
    returns = pnls / initial_balance
    mean_r = np.mean(returns)
    std_r = np.std(returns, ddof=1) if len(returns) > 1 else 1e-6
    sharpe = float((mean_r / std_r) * np.sqrt(trades_per_year)) if std_r > 0 else 0.0

    downside_r = returns[returns < 0]
    std_downside = np.std(downside_r, ddof=1) if len(downside_r) > 1 else std_r
    sortino = float((mean_r / std_downside) * np.sqrt(trades_per_year)) if std_downside > 0 else 0.0

    cagr = ((equity_curve[-1] / initial_balance) ** (1.0 / years) - 1.0) * 100.0 if equity_curve[-1] > 0 else -100.0
    calmar = (cagr / max_dd_pct) if max_dd_pct > 0 else 0.0

    # VaR & CVaR (99% Confidence Level)
    var_99 = float(abs(np.percentile(returns, 1.0))) * 100.0
    tail = returns[returns <= np.percentile(returns, 1.0)]
    cvar_99 = float(abs(np.mean(tail))) * 100.0 if len(tail) > 0 else var_99

    # Skewness, Kurtosis & Probabilistic Sharpe Ratio (PSR)
    skew = float(stats.skew(returns))
    kurt = float(stats.kurtosis(returns, fisher=True))
    kurt_p = kurt + 3.0
    sr_raw = mean_r / std_r if std_r > 0 else 0.0
    v_sr = (1.0 - skew * sr_raw + ((kurt_p - 1.0) / 4.0) * (sr_raw ** 2)) / max(1, total_trades - 1)
    psr = float(stats.norm.cdf(sr_raw / np.sqrt(max(1e-6, v_sr)))) if v_sr > 0 else 0.5

    # Monte Carlo 1,000 Resamplings
    n_sims = 1000
    mc_max_dds = []
    mc_final_equities = []
    mc_ruin_5pct = 0
    mc_ruin_10pct = 0
    mc_ruin_20pct = 0

    np.random.seed(42)
    for _ in range(n_sims):
        sim_pnls = np.random.choice(pnls, size=total_trades, replace=True)
        sim_eq = initial_balance + np.cumsum(sim_pnls)
        sim_peaks = np.maximum.accumulate(sim_eq)
        sim_dd = (sim_peaks - sim_eq) / sim_peaks * 100.0
        m_dd = np.max(sim_dd)
        
        mc_max_dds.append(m_dd)
        mc_final_equities.append(sim_eq[-1])
        
        if m_dd >= 5.0:
            mc_ruin_5pct += 1
        if m_dd >= 10.0:
            mc_ruin_10pct += 1
        if m_dd >= 20.0:
            mc_ruin_20pct += 1

    survival_rate_5dd = (1.0 - mc_ruin_5pct / n_sims) * 100.0
    survival_rate_10dd = (1.0 - mc_ruin_10pct / n_sims) * 100.0
    survival_rate_20dd = (1.0 - mc_ruin_20pct / n_sims) * 100.0
    mc_dd_95th = float(np.percentile(mc_max_dds, 95.0))
    mc_eq_median = float(np.median(mc_final_equities))

    # Asset-level PnL breakdown
    asset_breakdown = {}
    for t in all_oos_trades:
        sym = t["symbol"]
        asset_breakdown[sym] = asset_breakdown.get(sym, 0.0) + t["final_pnl"]

    # Baseline 12-asset stats for comparison
    b_trades = 959
    b_wr = 63.30
    b_pnl = 176.13
    b_ret = 1.76
    b_pf = 1.02
    b_sharpe = 0.16
    b_sortino = 0.16
    b_calmar = 0.22
    b_maxdd = 11.44
    b_cons = 7
    b_var99 = 1.59
    b_cvar99 = 2.00
    b_psr = 0.552
    b_payoff = 0.59
    b_surv10 = 28.6
    b_surv20 = 82.8

    print("\n" + "=" * 95)
    print("            BẢNG SO SÁNH KPI TRƯỚC VÀ SAU KHI TỐI ƯU DANH MỤC (OUT-OF-SAMPLE)")
    print("=" * 95)
    row_fmt = "{:<30} | {:<20} | {:<20} | {:<16}"
    print(row_fmt.format("Chỉ số định lượng (KPI)", "Trước (12 Assets)", "Sau (4 Core Assets)", "Mức cải thiện"))
    print("-" * 95)
    print(row_fmt.format("Tổng số lệnh OOS", f"{b_trades} trades", f"{total_trades} trades", f"-{b_trades - total_trades} lệnh rác"))
    print(row_fmt.format("Tỷ lệ thắng (Win Rate)", f"{b_wr:.2f}%", f"{win_rate:.2f}%", f"{win_rate - b_wr:+.2f}%"))
    print(row_fmt.format("Lợi nhuận ròng (Net PnL)", f"${b_pnl:+,.2f} ({b_ret:+.2f}%)", f"${net_pnl:+,.2f} ({return_pct:+.2f}%)", f"+${net_pnl - b_pnl:,.2f} ({return_pct/max(0.01, b_ret):.1f}x)"))
    print(row_fmt.format("Hệ số Lãi/Lỗ (Profit Factor)", f"{b_pf:.2f}", f"{profit_factor:.2f}", f"{profit_factor - b_pf:+.2f}"))
    print(row_fmt.format("Annualized Sharpe Ratio", f"{b_sharpe:.2f}", f"{sharpe:.2f}", f"{sharpe - b_sharpe:+.2f}"))
    print(row_fmt.format("Sortino Ratio (Downside)", f"{b_sortino:.2f}", f"{sortino:.2f}", f"{sortino - b_sortino:+.2f}"))
    print(row_fmt.format("Calmar Ratio (CAGR/MaxDD)", f"{b_calmar:.2f}", f"{calmar:.2f}", f"{calmar - b_calmar:+.2f}"))
    print(row_fmt.format("Max Drawdown (Sụt giảm max)", f"{b_maxdd:.2f}%", f"{max_dd_pct:.2f}% (${max_dd_usd:,.2f})", f"{max_dd_pct - b_maxdd:+.2f}% (Giảm rủi ro)"))
    print(row_fmt.format("Chuỗi lệnh thua max (Cons Loss)", f"{b_cons} lệnh", f"{max_cons} lệnh", f"{max_cons - b_cons:+d} lệnh"))
    print(row_fmt.format("1-Day 99% VaR", f"{b_var99:.2f}%", f"{var_99:.2f}%", f"{var_99 - b_var99:+.2f}%"))
    print(row_fmt.format("1-Day 99% CVaR", f"{b_cvar99:.2f}%", f"{cvar_99:.2f}%", f"{cvar_99 - b_cvar99:+.2f}%"))
    print(row_fmt.format("Probabilistic Sharpe (PSR)", f"{b_psr*100:.1f}%", f"{psr*100:.1f}%", f"{(psr - b_psr)*100:+.1f}%"))
    print(row_fmt.format("Payoff Ratio (Win/Loss)", f"{b_payoff:.2f}R", f"{payoff_ratio:.2f}R", f"{payoff_ratio - b_payoff:+.2f}R"))
    print("-" * 95)
    print("MÔ PHỎNG SỐNG SÓT MONTE CARLO (1,000 PATHS):")
    print(f"  • Xác suất sống sót ở Max DD ≤ 10%: Trước = {b_surv10:4.1f}%  ───►  Sau = {survival_rate_10dd:4.1f}% ({survival_rate_10dd - b_surv10:+.1f}%)")
    print(f"  • Xác suất sống sót ở Max DD ≤ 20%: Trước = {b_surv20:4.1f}%  ───►  Sau = {survival_rate_20dd:4.1f}% ({survival_rate_20dd - b_surv20:+.1f}%)")
    print(f"  • Vốn kỳ vọng trung vị ($10,000) : Trước = $10,218.75 ───►  Sau = ${mc_eq_median:,.2f}")
    print(f"  • Max Drawdown xấu nhất (95th)   : Trước = 26.73%     ───►  Sau = {mc_dd_95th:4.2f}%")
    print("=" * 95)

    print("\nCHI TIẾT PNL THEO TỪNG TÀI SẢN (4 CORE ASSETS):")
    print("-" * 50)
    for sym, pnl in sorted(asset_breakdown.items(), key=lambda x: x[1], reverse=True):
        print(f"  {sym:10s}: ${pnl:+8.2f}")
    print("=" * 95)

if __name__ == "__main__":
    run_comparison_audit()
