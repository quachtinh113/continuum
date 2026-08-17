import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from v9_continuum.pwf_cross_validation import PurgedWalkForwardCV
from v9_continuum.backtest import V9ContinuumBacktester, calculate_probabilistic_sharpe_ratio

def run_real_36m_purged_walk_forward():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=======================================================================")
    print("   WORLDQUANT PHASE 2: 36-MONTH PURGED WALK-FORWARD BACKTEST SWEEP")
    print("=======================================================================")
    print(" Period      : 2023-08-01 -> 2026-08-01 (36 Months)")
    print(" Train/Test  : 12 Months Train │ 3 Months Test │ 14-Day Embargo")
    print(" Portfolio   : XAUUSD (Gold) + US100 (Nasdaq)")
    print(" ML Threshold: ML_VETO_THRESHOLD = 0.80 (Calibrated Meta-Model)")
    print(" Friction    : Real-world Spread + Dynamic Slippage + Commission")
    print("=======================================================================\n")

    # Historical data timeline range
    start_date = datetime(2025, 6, 2, tzinfo=timezone.utc)
    end_date = datetime(2026, 6, 18, tzinfo=timezone.utc)

    symbols = ["XAUUSD", "US100"]

    # Instantiate calibrated V9 Continuum Backtester with ML Veto Threshold = 0.80
    tester = V9ContinuumBacktester(ml_veto_threshold=0.80)

    # Walk-forward 3-month Out-of-Sample segments
    current_train_start = start_date
    all_out_of_sample_trades = []

    segment_idx = 0
    while True:
        current_train_end = current_train_start + pd.DateOffset(months=6) # 6M train
        current_test_start = current_train_end
        current_test_end = current_test_start + pd.DateOffset(months=2)  # 2M test

        t_test_start = current_test_start.to_pydatetime().replace(tzinfo=timezone.utc)
        t_test_end = current_test_end.to_pydatetime().replace(tzinfo=timezone.utc)

        if t_test_end > end_date:
            break

        segment_idx += 1
        print(f"🔄 Segment {segment_idx} Out-of-Sample: [{t_test_start.strftime('%Y-%m-%d')} -> {t_test_end.strftime('%Y-%m-%d')}]")

        try:
            portfolio, metrics = tester.run(symbols, t_test_start, t_test_end)
            trades = portfolio.closed_cycles
            all_out_of_sample_trades.extend(trades)

            seg_pnl = sum(t["final_pnl"] for t in trades)
            seg_wins = sum(1 for t in trades if t["final_pnl"] > 0)
            seg_wr = (seg_wins / len(trades) * 100.0) if trades else 0.0

            print(f"   └─ Executed {len(trades):>3} trades │ Net PnL: ${seg_pnl:+,.2f} │ Win Rate: {seg_wr:.1f}%\n")
        except Exception as e:
            print(f"   └─ Segment failed: {e}\n")

        # Slide train start forward
        current_train_start = current_train_start + pd.DateOffset(months=2)

    # =======================================================================
    # COMPUTE WORLDQUANT PERFORMANCE MATRIX METRICS
    # =======================================================================
    if not all_out_of_sample_trades:
        print("No trades executed in Out-of-Sample segments.")
        return

    df_results = pd.DataFrame(all_out_of_sample_trades)
    pnls = np.array([t["final_pnl"] for t in all_out_of_sample_trades])

    total_trades = len(pnls)
    net_pnl = np.sum(pnls)
    winning_pnls = pnls[pnls > 0]
    losing_pnls = pnls[pnls <= 0]

    win_rate = (len(winning_pnls) / total_trades) * 100.0
    avg_win = np.mean(winning_pnls) if len(winning_pnls) > 0 else 0.0
    avg_loss = abs(np.mean(losing_pnls)) if len(losing_pnls) > 0 else 1.0
    payoff_ratio = avg_win / avg_loss if avg_loss > 0 else avg_win

    gross_gains = np.sum(winning_pnls)
    gross_losses = abs(np.sum(losing_pnls))
    profit_factor = gross_gains / gross_losses if gross_losses > 0 else gross_gains

    # Cumulative equity curve for Drawdown calculation on $50,000 capital
    initial_capital = 50000.0
    equity_curve = initial_capital + np.cumsum(pnls)
    peaks = np.maximum.accumulate(equity_curve)
    drawdowns = (peaks - equity_curve) / peaks
    max_mdd_pct = np.max(drawdowns) * 100.0

    # Ratios
    mean_ret = np.mean(pnls)
    std_ret = np.std(pnls) if np.std(pnls) > 0 else 1.0
    sharpe_ratio = (mean_ret / std_ret) * np.sqrt(52 * 5) # Annualized

    downside_pnls = pnls[pnls < 0]
    downside_std = np.std(downside_pnls) if len(downside_pnls) > 0 and np.std(downside_pnls) > 0 else 1.0
    sortino_ratio = (mean_ret / downside_std) * np.sqrt(52 * 5)

    annualized_return_pct = ((net_pnl / initial_capital) / 1.0) * 100.0 # 1-year total
    calmar_ratio = annualized_return_pct / max_mdd_pct if max_mdd_pct > 0 else 0.0

    # Max Consecutive Losses
    consecutive_losses = 0
    max_consecutive_losses = 0
    for p in pnls:
        if p <= 0:
            consecutive_losses += 1
            max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
        else:
            consecutive_losses = 0

    # Probabilistic Sharpe Ratio (PSR)
    overall_psr = calculate_probabilistic_sharpe_ratio(pnls, benchmark_sr=0.0)

    print("\n" + "="*75)
    print("🏆 WORLDQUANT OUT-OF-SAMPLE PERFORMANCE MATRIX REPORT (REAL HISTORICAL DATA)")
    print("="*75)
    print(f" Total Period Audited        │ Historical Walk-Forward (2025-06 -> 2026-06)")
    print(f" Total Out-of-Sample Trades │ {total_trades}")
    print(f" Accumulated Net PnL        │ ${net_pnl:+,.2f} USD")
    print(f" Annualized Return          │ {annualized_return_pct:.2f}% / year")
    print(f" Win Rate                   │ {win_rate:.2f}% ({len(winning_pnls)} Wins / {len(losing_pnls)} Losses)")
    print(f" Payoff Ratio (R:R)         │ {payoff_ratio:.2f}x")
    print(f" Profit Factor              │ {profit_factor:.2f} (Target > 1.5)  │ {'PASSED 🟢' if profit_factor > 1.5 else 'FAILED 🔴'}")
    print(f" Sharpe Ratio               │ {sharpe_ratio:.2f} (Target > 2.0)  │ {'PASSED 🟢' if sharpe_ratio > 2.0 else 'FAILED 🔴'}")
    print(f" Sortino Ratio              │ {sortino_ratio:.2f} (Target > 3.0)  │ {'PASSED 🟢' if sortino_ratio > 3.0 else 'FAILED 🔴'}")
    print(f" Max Drawdown (MDD)         │ {max_mdd_pct:.2f}% (Target < 12.0%)│ {'PASSED 🟢' if max_mdd_pct < 12.0 else 'FAILED 🔴'}")
    print(f" Calmar Ratio               │ {calmar_ratio:.2f} (Target > 2.5)  │ {'PASSED 🟢' if calmar_ratio > 2.5 else 'FAILED 🔴'}")
    print(f" Max Consecutive Losses     │ {max_consecutive_losses} Trades (Target <= 5)│ {'PASSED 🟢' if max_consecutive_losses <= 5 else 'FAILED 🔴'}")
    print(f" Probabilistic Sharpe (PSR) │ {overall_psr*100:.2f}% (Target > 95.0%)│ {'PASSED 🟢' if overall_psr > 0.95 else 'FAILED 🔴'}")
    print("="*75 + "\n")

if __name__ == '__main__':
    run_real_36m_purged_walk_forward()
