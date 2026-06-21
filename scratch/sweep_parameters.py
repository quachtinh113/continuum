import sys
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pandas as pd

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.backtest_engine import BacktestEngine
from config import settings

def run_test(engine, symbols, start_date, end_date, entry_threshold, tp_mult, dca_mults):
    # Override settings dynamically
    settings.ML_ENTRY_SAFE_THRESHOLD = entry_threshold
    settings.TAKE_PROFIT_ATR_MULTIPLIER = tp_mult
    settings.DCA_LAYER_1_ATR = dca_mults[0]
    settings.DCA_LAYER_2_ATR = dca_mults[1]
    settings.DCA_LAYER_3_ATR = dca_mults[2]
    
    # Run backtest
    portfolio, metrics = engine.run_backtest(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        initial_balance=10000.0,
        no_time_stop=False
    )
    return metrics

def main():
    print("Initializing Parameter Sweep (Optimized)...")
    engine = BacktestEngine(data_dir="data/historical")
    
    end_date = datetime(2026, 6, 11, tzinfo=timezone.utc)
    start_date = end_date - timedelta(days=180)
    
    # Focus on 4 core symbols to reduce backtest duration
    symbols_to_test = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
    available_symbols = [s for s in symbols_to_test if (Path("data/historical") / f"{s}_M15.csv").exists()]
    
    # 6 representative test runs to isolate variables
    # Format: (ML_ENTRY_SAFE_THRESHOLD, TAKE_PROFIT_ATR_MULTIPLIER, (DCA_L1, DCA_L2, DCA_L3))
    grid = [
        # 1. Baseline: permissive entry, current TP, standard step
        (0.85, 1.5, (2.0, 3.0, 4.0)), 
        # 2. Strict Entry: strict ML filter, standard TP
        (0.35, 1.5, (2.0, 3.0, 4.0)),
        # 3. Balanced Entry: moderate entry filter, standard TP
        (0.55, 1.5, (2.0, 3.0, 4.0)),
        # 4. Balanced Entry + Higher TP: moderate filter, higher TP
        (0.55, 2.0, (2.0, 3.0, 4.0)),
        # 5. Balanced Entry + Closer Spacing: moderate filter, close DCA
        (0.55, 1.5, (1.5, 2.5, 3.5)),
        # 6. Balanced Entry + Wider Spacing: moderate filter, wide DCA
        (0.55, 1.5, (2.5, 3.5, 4.5)),
    ]
    
    results = []
    
    for i, (entry_th, tp_mult, dca_tiers) in enumerate(grid):
        print(f"\nRunning test {i+1}/{len(grid)}: Entry_Th={entry_th}, TP_Mult={tp_mult}, DCA_Steps={dca_tiers}...")
        try:
            m = run_test(engine, available_symbols, start_date, end_date, entry_th, tp_mult, dca_tiers)
            res = {
                "Run": i + 1,
                "Entry_Th": entry_th,
                "TP_Mult": tp_mult,
                "DCA_Steps": str(dca_tiers),
                "Profit_USD": m["total_profit_usd"],
                "Profit_Pct": m["profit_percent"],
                "Trades": m["total_cycles"],
                "Win_Rate": m["win_rate"],
                "Profit_Factor": m["profit_factor"],
                "Max_DD_Pct": m["max_drawdown_percent"],
                "BE_Exits": m["reasons"].get("BREAK_EVEN", 0),
                "Veto_Exits": m["reasons"].get("ML_VETO_CLOSE", 0),
                "TP_Exits": m["reasons"].get("TAKE_PROFIT", 0)
            }
            results.append(res)
            print(f"Result: Profit={res['Profit_USD']:.2f} ({res['Profit_Pct']:.2f}%), Trades={res['Trades']}, WinRate={res['Win_Rate']:.2f}%, MaxDD={res['Max_DD_Pct']:.2f}%")
        except Exception as e:
            print(f"Failed run {i+1}: {e}")
            
    # Output markdown report
    df = pd.DataFrame(results)
    df.to_csv("sweep_results.csv", index=False)
    
    report_path = Path("sweep_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Parameter Sweep Optimization Report\n\n")
        f.write("This report displays the performance across 4 core symbols (EURUSD, GBPUSD, USDJPY, XAUUSD) over 6 months.\n\n")
        f.write("## Matrix Results Table\n\n")
        # Custom markdown table generator
        headers = df.columns.tolist()
        table_lines = []
        table_lines.append("| " + " | ".join(headers) + " |")
        table_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for _, row in df.iterrows():
            line = "| " + " | ".join(str(row[col]) for col in headers) + " |"
            table_lines.append(line)
        f.write("\n".join(table_lines))
        f.write("\n\n## Recommendations\n")
        
        safe_runs = df[df["Max_DD_Pct"] < 6.0]
        if not safe_runs.empty:
            best_run = safe_runs.loc[safe_runs["Profit_USD"].idxmax()]
            f.write(f"- **Best Performing Safe Run (Max DD < 6%):** Run {best_run['Run']}\n")
            f.write(f"  - **ML Entry Safe Threshold:** {best_run['Entry_Th']}\n")
            f.write(f"  - **Take Profit ATR Multiplier:** {best_run['TP_Mult']}\n")
            f.write(f"  - **DCA Spacing Steps:** {best_run['DCA_Steps']}\n")
            f.write(f"  - **Net Profit:** ${best_run['Profit_USD']:.2f} ({best_run['Profit_Pct']:.2f}%)\n")
            f.write(f"  - **Max Drawdown:** {best_run['Max_DD_Pct']:.2f}%\n")
            f.write(f"  - **Total Trades:** {best_run['Trades']}\n")
            f.write(f"  - **Win Rate:** {best_run['Win_Rate']:.2f}%\n")
        else:
            f.write("- No run achieved drawdown below 6%.\n")
            
    print(f"\nSweep complete! Report written to {report_path.absolute()}")

if __name__ == '__main__':
    main()
