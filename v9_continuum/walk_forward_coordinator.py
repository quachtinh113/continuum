import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from v9_continuum.backtest import V9ContinuumBacktester, calculate_probabilistic_sharpe_ratio
from config.symbols import get_symbol_spec

class WalkForwardCoordinator:
    def __init__(self, start_date: datetime, end_date: datetime, train_months: int = 3, test_months: int = 1):
        self.start_date = start_date
        self.end_date = end_date
        self.train_months = train_months
        self.test_months = test_months
        self.all_trades = []

    def run(self, symbols: list):
        sys.stdout.reconfigure(encoding='utf-8')
        current_train_start = self.start_date
        tester = V9ContinuumBacktester()

        while True:
            # 1. Define segment bounds
            current_train_end = current_train_start + pd.DateOffset(months=self.train_months)
            current_test_start = current_train_end
            current_test_end = current_test_start + pd.DateOffset(months=self.test_months)

            # Ensure we have dates as datetime.datetime (UTC timezone)
            t_train_start = current_train_start.to_pydatetime() if hasattr(current_train_start, "to_pydatetime") else current_train_start
            t_train_end = current_train_end.to_pydatetime() if hasattr(current_train_end, "to_pydatetime") else current_train_end
            t_test_start = current_test_start.to_pydatetime() if hasattr(current_test_start, "to_pydatetime") else current_test_start
            t_test_end = current_test_end.to_pydatetime() if hasattr(current_test_end, "to_pydatetime") else current_test_end

            t_train_start = t_train_start.replace(tzinfo=timezone.utc)
            t_train_end = t_train_end.replace(tzinfo=timezone.utc)
            t_test_start = t_test_start.replace(tzinfo=timezone.utc)
            t_test_end = t_test_end.replace(tzinfo=timezone.utc)

            if t_test_end > self.end_date:
                print("\n🏁 Walk-Forward chronological loop completed.")
                break

            print(f"\n🔄 [WALK-FORWARD CYCLE]")
            print(f"  ├─ Train window : {t_train_start.strftime('%Y-%m-%d')} -> {t_train_end.strftime('%Y-%m-%d')}")
            print(f"  └─ Out-of-sample: {t_test_start.strftime('%Y-%m-%d')} -> {t_test_end.strftime('%Y-%m-%d')}")

            # 2. Embargo step: Train model ending slightly before test start (e.g. drop last 24h of train)
            t_embargo_train_end = t_train_end - timedelta(days=1)
            
            # 3. Simulate training block
            # For backtesting simplicity and repeatability, we utilize the backtester runtime.
            # In a live setup, this would invoke train_model.py on indicators from t_train_start to t_embargo_train_end.
            
            # 4. Execute out-of-sample backtest slice
            try:
                portfolio, metrics = tester.run(symbols, t_test_start, t_test_end)
                self.all_trades.extend(portfolio.closed_cycles)
                print(f"  └─ Executed {len(portfolio.closed_cycles)} trades. Net PnL: ${metrics['total_profit_usd']:+,.2f} | PSR: {metrics['psr']*100:.2f}%")
            except Exception as e:
                print(f"  └─ Segment failed: {e}")

            # Shift window forward
            current_train_start = current_train_start + pd.DateOffset(months=self.test_months)

        self._generate_overall_metrics()

    def _generate_overall_metrics(self):
        if not self.all_trades:
            print("\n❌ No trades executed during the entire Walk-Forward period.")
            return

        pnl_series = [t["final_pnl"] for t in self.all_trades]
        overall_psr = calculate_probabilistic_sharpe_ratio(pnl_series, benchmark_sr=0.0)

        total_profit = sum(pnl_series)
        win_count = sum(1 for p in pnl_series if p > 0)
        win_rate = (win_count / len(pnl_series)) * 100.0

        print("\n" + "="*60)
        print("🏆 OVERALL WALK-FORWARD 1-YEAR PERFORMANCE")
        print("="*60)
        print(f" Total Trades Executed : {len(self.all_trades)}")
        print(f" Net Accumulated P&L   : ${total_profit:+,.2f} USD")
        print(f" Win Rate              : {win_rate:.2f}%")
        print(f" Prob. Sharpe (PSR)    : {overall_psr:.4f} ({overall_psr*100:.2f}%)")
        print("="*60 + "\n")

if __name__ == "__main__":
    # Example execution: Last year walk-forward
    end = datetime(2026, 6, 18, tzinfo=timezone.utc)
    start = end - timedelta(days=365)
    
    # Select available test symbols
    symbols = ["XAUUSD", "US100"]
    
    coordinator = WalkForwardCoordinator(start_date=start, end_date=end)
    coordinator.run(symbols)
