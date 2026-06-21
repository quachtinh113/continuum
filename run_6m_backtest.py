import sys
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.backtest_engine import BacktestEngine
from config.symbols import SYMBOLS

def main():
    print("Initializing BacktestEngine...")
    engine = BacktestEngine(data_dir="data/historical")
    
    # 6 months back from 2026-06-11
    end_date = datetime(2026, 6, 11, tzinfo=timezone.utc)
    start_date = end_date - timedelta(days=180)
    
    symbols_to_test = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "US100", "US500", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]
    # Check which symbols actually have data
    available_symbols = []
    for s in symbols_to_test:
        if (Path("data/historical") / f"{s}_M15.csv").exists():
            available_symbols.append(s)
    
    print(f"Running backtest for symbols: {available_symbols}")
    print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    portfolio, metrics = engine.run_backtest(
        symbols=available_symbols,
        start_date=start_date,
        end_date=end_date,
        initial_balance=10000.0,
        no_time_stop=False
    )
    
    print("\n" + "="*50)
    print("BACKTEST RESULTS")
    print("="*50)
    for k, v in metrics.items():
        if k == "reasons":
            print(f"Close Reasons:")
            for reason, count in v.items():
                print(f"  - {reason}: {count}")
        else:
            print(f"{k}: {v}")

    # Generate a markdown report
    report_path = Path("backtest_6m_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 6-Month Backtest Report\n\n")
        f.write(f"**Period:** {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}\n")
        f.write(f"**Symbols:** {', '.join(available_symbols)}\n\n")
        
        f.write("## Performance Metrics\n")
        f.write(f"- **Initial Balance:** ${metrics['initial_balance']:.2f}\n")
        f.write(f"- **Final Balance:** ${metrics['final_balance']:.2f}\n")
        f.write(f"- **Total Profit:** ${metrics['total_profit_usd']:.2f} ({metrics['profit_percent']:.2f}%)\n")
        f.write(f"- **Total Trades (Cycles):** {metrics['total_cycles']}\n")
        f.write(f"- **Win Rate:** {metrics['win_rate']:.2f}%\n")
        f.write(f"- **Profit Factor:** {metrics['profit_factor']:.2f}\n")
        f.write(f"- **Gross Profit:** ${metrics['gross_profit']:.2f}\n")
        f.write(f"- **Gross Loss:** ${metrics['gross_loss']:.2f}\n")
        f.write(f"- **Max Drawdown:** ${metrics['max_drawdown_usd']:.2f} ({metrics['max_drawdown_percent']:.2f}%)\n\n")
        
        f.write("## Trading Statistics\n")
        if metrics['total_cycles'] > 0:
            avg_trades_per_day = metrics['total_cycles'] / 180
            avg_profit_per_trade = metrics['total_profit_usd'] / metrics['total_cycles']
        else:
            avg_trades_per_day = 0
            avg_profit_per_trade = 0
        f.write(f"- **Average Trades / Day:** {avg_trades_per_day:.2f}\n")
        f.write(f"- **Average Profit / Trade:** ${avg_profit_per_trade:.2f}\n")
        f.write(f"- **Average Holding Hours:** {metrics['avg_holding_hours']:.1f}\n")
        f.write(f"- **Average DCA Layers:** {metrics['avg_dca_layers']:.2f}\n")
        f.write(f"- **Max DCA Layers Reached:** {metrics['max_dca_reached']}\n\n")
        
        f.write("## Exit Reasons Breakdown\n")
        for reason, count in metrics['reasons'].items():
            f.write(f"- **{reason}:** {count}\n")
            
    print(f"\nReport saved to {report_path.absolute()}")

if __name__ == '__main__':
    main()
