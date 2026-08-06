import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add workspace root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from v9_continuum.backtest import V9ContinuumBacktester

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    # Set veto threshold to 1.0 to disable vetoing
    tester = V9ContinuumBacktester(ml_veto_threshold=1.0)
    symbols = ["XAUUSD"]
    
    start_date = datetime(2025, 6, 2, tzinfo=timezone.utc)
    end_date = datetime(2026, 6, 18, tzinfo=timezone.utc)
    
    print("Running diagnostic backtest on XAUUSD with ml_veto_threshold=1.0...")
    portfolio, metrics = tester.run(symbols, start_date, end_date, initial_balance=10000.0)
    
    print(f"Total closed trades: {len(portfolio.closed_cycles)}")
    if len(portfolio.closed_cycles) > 0:
        pnl = sum(c['final_pnl'] for c in portfolio.closed_cycles)
        print(f"Total PnL: ${pnl:.2f}")

if __name__ == '__main__':
    main()
