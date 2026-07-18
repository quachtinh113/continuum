import os
import sys
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

def parse_args():
    parser = argparse.ArgumentParser(description="V9 Continuum Monte Carlo Stress-Tester")
    parser.add_argument("--file", type=str, default="trades_history.csv", help="Path to trades history CSV.")
    parser.add_argument("--capital", type=float, default=10000.0, help="Initial capital simulation base.")
    parser.add_argument("--ruin-pct", type=float, default=20.0, help="Drawdown percentage defined as 'Ruin' (e.g. 20.0 for 20% DD).")
    parser.add_argument("--simulations", type=int, default=10000, help="Number of Monte Carlo paths.")
    return parser.parse_args()

def run_stress_test():
    sys.stdout.reconfigure(encoding='utf-8')
    args = parse_args()
    
    csv_path = Path(args.file)
    if not csv_path.exists():
        # Fallback to generating simulated trades if history file is not found
        print(f"⚠️ Trades file '{args.file}' not found. Generating mock trades for validation...")
        np.random.seed(42)
        # Mock 500 trades with 68% win rate, average win $30, average loss -$50
        wins = np.random.normal(30.0, 10.0, 340)
        losses = np.random.normal(-50.0, 15.0, 160)
        trade_pnl = np.concatenate([wins, losses])
        np.random.shuffle(trade_pnl)
    else:
        df = pd.read_csv(csv_path)
        if "final_pnl" in df.columns:
            trade_pnl = df["final_pnl"].values
        elif "profit" in df.columns:
            trade_pnl = df["profit"].values
        elif "Profit (USD)" in df.columns:
            trade_pnl = df["Profit (USD)"].values
        else:
            print("Error: Could not find 'final_pnl', 'profit', or 'Profit (USD)' column in CSV.")
            return

    num_trades = len(trade_pnl)
    if num_trades < 10:
        print("Error: Need at least 10 trades to run a valid Monte Carlo simulation.")
        return

    print("============================================================")
    print(f"🎲 RUNNING MONTE CARLO STRESS-TEST (N={args.simulations})")
    print(f"   ├─ Number of Trades: {num_trades}")
    print(f"   ├─ Starting Capital: ${args.capital:,.2f}")
    print(f"   ├─ Ruin Threshold  : -{args.ruin_pct}% (${args.capital * (1 - args.ruin_pct/100):,.2f})")
    print("============================================================")

    drawdowns = []
    ruined_count = 0

    for _ in range(args.simulations):
        # Bootstrap sampling with replacement
        shuffled_pnl = np.random.choice(trade_pnl, size=num_trades, replace=True)
        equity_curve = args.capital + np.cumsum(shuffled_pnl)
        
        # Calculate Peak-to-Trough Drawdown
        peaks = np.maximum.accumulate(equity_curve)
        peaks = np.maximum(peaks, args.capital) # Ensure starting balance acts as initial peak
        dds = (peaks - equity_curve) / peaks * 100.0
        max_dd = np.max(dds)
        drawdowns.append(max_dd)
        
        if max_dd >= args.ruin_pct:
            ruined_count += 1

    prob_of_ruin = (ruined_count / args.simulations) * 100.0
    median_dd = np.median(drawdowns)
    dd_95 = np.percentile(drawdowns, 95)
    dd_99 = np.percentile(drawdowns, 99)

    print(f"\n📊 RISK SUMMARY STATISTICS:")
    print(f"  ├─ Median Max Drawdown     : {median_dd:.2f}%")
    print(f"  ├─ 95th Percentile DD (VaR) : {dd_95:.2f}%")
    print(f"  ├─ 99th Percentile DD (Tail): {dd_99:.2f}%")
    print(f"  └─ Probability of Ruin      : {prob_of_ruin:.2f}%")
    print("============================================================\n")

if __name__ == "__main__":
    run_stress_test()
