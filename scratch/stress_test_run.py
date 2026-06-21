"""
NowTrading 2.1 — Historical Stress Test Runner
Runs backtest over 2026-01-01 to 2026-06-15 with Scenario C Aggressive settings,
variable spreads, and cumulative daily drawdown controls.
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from src.backtest_engine import BacktestEngine


def main():
    print("==============================================================")
    print("   NOWTRADING 2.1 — AGGRESSIVE SCENARIO C STRESS TEST RUNNER")
    print("==============================================================")

    # 1. Force settings to Aggressive Scenario C parameters
    settings.FX_BASE_LOT = 0.02
    settings.COMMODITY_BASE_LOT = 0.01
    settings.CRYPTO_BASE_LOT = 0.01
    settings.MAX_LOT_SIZE = 0.10
    settings.MAX_DAILY_DRAWDOWN_USD = 120.0

    print("Settings Applied:")
    print(f"  - FX Base Lot: {settings.FX_BASE_LOT}")
    print(f"  - Gold/Commodity Base Lot: {settings.COMMODITY_BASE_LOT}")
    print(f"  - Crypto Base Lot: {settings.CRYPTO_BASE_LOT}")
    print(f"  - Max Lot Size: {settings.MAX_LOT_SIZE}")
    print(f"  - Max Daily Drawdown (Hard Stop Limit): ${settings.MAX_DAILY_DRAWDOWN_USD}")
    print("--------------------------------------------------------------")

    # 2. Instantiate BacktestEngine
    engine = BacktestEngine(data_dir="data/historical")

    symbols = ["EURUSD", "GBPUSD", "XAUUSD", "BTCUSD"]
    start_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2026, 6, 15, tzinfo=timezone.utc)

    print(f"Loading data for {symbols}...")
    print(f"Test Range: {start_date.date()} to {end_date.date()}")
    print("Executing look-ahead-free backtest with spread penalty & dynamic daily drawdown checks...")

    try:
        portfolio, metrics = engine.run_backtest(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            initial_balance=1015.23,
            use_spread=True,
        )
    except Exception as e:
        print(f"Error during backtest execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n--------------------------------------------------------------")
    print("                       BACKTEST RESULTS")
    print("--------------------------------------------------------------")
    print(f"Initial Balance:        ${metrics['initial_balance']:.2f}")
    print(f"Final Balance:          ${metrics['final_balance']:.2f}")
    print(f"Net Profit:             ${metrics['total_profit_usd']:.2f} ({metrics['profit_percent']:.2f}%)")
    print(f"Total Cycles:           {metrics['total_cycles']}")
    print(f"Win Rate:               {metrics['win_rate']:.2f}%")
    print(f"Profit Factor:          {metrics['profit_factor']:.2f}")

    # Calculate custom Recovery Factor
    net_profit = metrics['total_profit_usd']
    max_dd_usd = metrics['max_drawdown_usd']
    max_dd_pct = metrics['max_drawdown_percent']
    
    recovery_factor = net_profit / max_dd_usd if max_dd_usd > 0 else float('inf')
    print(f"Max Drawdown:           ${max_dd_usd:.2f} ({max_dd_pct:.2f}%)")
    print(f"Recovery Factor:        {recovery_factor:.2f}")
    print(f"Avg Holding Hours:      {metrics['avg_holding_hours']:.1f}h")
    print(f"Avg DCA Layers Used:    {metrics['avg_dca_layers']:.2f}")
    print(f"Max DCA Layer Reached:  {metrics['max_dca_reached']}")
    
    print("\n--- Close Reasons Breakdown ---")
    for reason, count in metrics['reasons'].items():
        print(f"  - {reason}: {count}")

    # 3. Analyze Survival Metrics and Hard Stop hits
    # Let's count days where realized + open floating loss exceeded MAX_DAILY_DRAWDOWN_USD.
    # In VirtualPortfolio, self.daily_losses tracks realized daily loss.
    # But wait, did we hit daily drawdown limit hard stop during execution?
    # Let's check how many times portfolio was blocked from trading because of daily drawdown.
    # We can inspect the portfolio's closed cycles to see if any cycle closed due to daily drawdown, 
    # or if we had extreme drawdown days.
    
    print("\n--- Risk & Survival Analysis ---")
    
    # Track daily equity drawdown peaks and counts
    extreme_loss_days = {}
    for date_str, loss in portfolio.daily_losses.items():
        if loss >= settings.MAX_DAILY_DRAWDOWN_USD:
            extreme_loss_days[date_str] = loss
            
    print(f"Realized Daily Hard Stop ($120) Violations: {len(extreme_loss_days)}")
    for date_str, loss in extreme_loss_days.items():
        print(f"  - {date_str}: Realized Loss ${loss:.2f}")

    # Let's check max floating loss at any step
    max_floating_loss = 0.0
    for step in portfolio.equity_curve:
        bal = step["balance"]
        eq = step["equity"]
        floating = bal - eq
        if floating > max_floating_loss:
            max_floating_loss = floating
            
    print(f"Max Open Floating Loss (Gồng lỗ trạng thái): ${max_floating_loss:.2f}")


if __name__ == "__main__":
    main()
