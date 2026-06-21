import sys
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pandas as pd

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.backtest_engine import BacktestEngine
from config import settings

def run_test(engine, symbols, start_date, end_date, activation_mult, buffer_mult):
    # Override settings dynamically
    settings.BREAK_EVEN_ACTIVATION_ATR_MULTIPLIER = activation_mult
    settings.BREAK_EVEN_BUFFER_ATR_MULTIPLIER = buffer_mult
    
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
    print("Initializing Break-Even Parameter Sweep...")
    engine = BacktestEngine(data_dir="data/historical")
    
    end_date = datetime(2026, 6, 11, tzinfo=timezone.utc)
    start_date = end_date - timedelta(days=180)
    
    # Core symbols to sweep (FX Majors + Gold)
    symbols_to_test = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
    available_symbols = [s for s in symbols_to_test if (Path("data/historical") / f"{s}_M15.csv").exists()]
    
    # Parameter grid: 3 activation multipliers x 3 buffer multipliers = 9 configurations
    activation_mults = [0.75, 1.0, 1.25]
    buffer_mults = [-0.05, 0.0, 0.05]
    
    grid = []
    for act in activation_mults:
        for buf in buffer_mults:
            grid.append((act, buf))
            
    # Add the baseline case (0.75 activation, 0.0 buffer)
    # We will mark it as the reference in our report.

    results = []
    
    print(f"Sweeping {len(grid)} configurations on symbols: {available_symbols}")
    
    for i, (act, buf) in enumerate(grid):
        print(f"[{i+1}/{len(grid)}] Testing Act_Mult={act:.2f}, Buf_Mult={buf:.2f}...")
        try:
            m = run_test(engine, available_symbols, start_date, end_date, act, buf)
            res = {
                "Run": i + 1,
                "Act_Mult": act,
                "Buf_Mult": buf,
                "Profit_USD": m["total_profit_usd"],
                "Profit_Pct": m["profit_percent"],
                "Trades": m["total_cycles"],
                "Win_Rate": m["win_rate"],
                "Profit_Factor": m["profit_factor"],
                "Max_DD_Pct": m["max_drawdown_percent"],
                "BE_Exits": m["reasons"].get("BREAK_EVEN", 0),
                "TP_Exits": m["reasons"].get("TAKE_PROFIT", 0),
                "ML_Exits": m["reasons"].get("ML_VETO_CLOSE", 0),
                "Hard_Stop_Exits": m["reasons"].get("FORCE_CLOSE_RR_LIMIT", 0),
            }
            results.append(res)
            print(f" -> Profit={res['Profit_USD']:.2f} ({res['Profit_Pct']:.2f}%), BE Exits={res['BE_Exits']}, WinRate={res['Win_Rate']:.2f}%")
        except Exception as e:
            print(f"Failed run: {e}")
            
    # Output report
    df = pd.DataFrame(results)
    df.to_csv("sweep_be_results.csv", index=False)
    
    # Generate report file
    report_path = Path("sweep_be_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Break-Even Logic Optimization Report\n\n")
        f.write(f"**Period:** {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} (6 months)\n")
        f.write(f"**Symbols:** {', '.join(available_symbols)}\n\n")
        f.write("## Parameter Grid Sweep Results\n\n")
        
        headers = df.columns.tolist()
        f.write("| " + " | ".join(headers) + " |\n")
        f.write("| " + " | ".join(["---"] * len(headers)) + " |\n")
        for _, row in df.iterrows():
            # Bold the baseline run (Act=0.75, Buf=0.0)
            is_baseline = abs(row["Act_Mult"] - 0.75) < 0.01 and abs(row["Buf_Mult"] - 0.0) < 0.01
            line = []
            for col in headers:
                val = row[col]
                # Format floats for cleaner output
                if isinstance(val, float):
                    val_str = f"{val:.2f}"
                else:
                    val_str = str(val)
                if is_baseline:
                    line.append(f"**{val_str}**")
                else:
                    line.append(val_str)
            f.write("| " + " | ".join(line) + " |\n")
            
        f.write("\n## Analysis and Key Findings\n")
        
        # Find best runs
        best_profit = df.loc[df["Profit_USD"].idxmax()]
        f.write(f"- **Top Profit Run:** Run {int(best_profit['Run'])} with Act_Mult={best_profit['Act_Mult']:.2f}, Buf_Mult={best_profit['Buf_Mult']:.2f}\n")
        f.write(f"  - Net Profit: ${best_profit['Profit_USD']:.2f} ({best_profit['Profit_Pct']:.2f}%)\n")
        f.write(f"  - Win Rate: {best_profit['Win_Rate']:.2f}%\n")
        f.write(f"  - Profit Factor: {best_profit['Profit_Factor']:.2f}\n")
        f.write(f"  - Max DD: {best_profit['Max_DD_Pct']:.2f}%\n")
        f.write(f"  - Break-Even Exits: {int(best_profit['BE_Exits'])}\n\n")
        
        # Find baseline metrics for comparison
        baseline = df[(abs(df["Act_Mult"] - 0.75) < 0.01) & (abs(df["Buf_Mult"] - 0.0) < 0.01)]
        if not baseline.empty:
            b = baseline.iloc[0]
            f.write(f"- **Baseline Run (Act_Mult=0.75, Buf_Mult=0.00):**\n")
            f.write(f"  - Net Profit: ${b['Profit_USD']:.2f} ({b['Profit_Pct']:.2f}%)\n")
            f.write(f"  - Win Rate: {b['Win_Rate']:.2f}%\n")
            f.write(f"  - Max DD: {b['Max_DD_Pct']:.2f}%\n")
            f.write(f"  - Break-Even Exits: {int(b['BE_Exits'])}\n")

    print(f"\nSweep complete! Report written to {report_path.absolute()}")

if __name__ == '__main__':
    main()
