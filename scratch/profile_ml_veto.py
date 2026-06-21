import sys
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pandas as pd

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.backtest_engine import BacktestEngine
from config import settings

def run_backtest(engine, symbols, start_dt, end_dt, ml_active):
    # Set BE settings to optimal
    settings.BREAK_EVEN_ACTIVATION_ATR_MULTIPLIER = 1.25
    settings.BREAK_EVEN_BUFFER_ATR_MULTIPLIER = -0.05
    settings.ML_GATEKEEPER_ACTIVE = ml_active
    
    portfolio, metrics = engine.run_backtest(
        symbols=symbols,
        start_date=start_dt,
        end_date=end_dt,
        initial_balance=10000.0,
        no_time_stop=False
    )
    return portfolio, metrics

def main():
    print("Initializing ML Veto Profiler...")
    engine = BacktestEngine(data_dir="data/historical")
    
    end_date = datetime(2026, 6, 11, tzinfo=timezone.utc)
    start_date = end_date - timedelta(days=180)
    
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
    available_symbols = [s for s in symbols if (Path("data/historical") / f"{s}_M15.csv").exists()]
    
    print(f"Running baseline backtest WITH ML Veto on {available_symbols}...")
    port_with_ml, metrics_with_ml = run_backtest(engine, available_symbols, start_date, end_date, ml_active=True)
    
    print(f"Running counterfactual backtest WITHOUT ML Veto...")
    port_no_ml, metrics_no_ml = run_backtest(engine, available_symbols, start_date, end_date, ml_active=False)
    
    print("\nAnalyzing counterfactuals...")
    
    # Map of trades: key = (symbol, entry_time)
    # entry_time needs to be formatted to ignore tiny timezone differences in comparison
    def get_key(cycle):
        return (cycle.symbol, cycle.entry_time.strftime("%Y-%m-%d %H:%M"))
        
    trades_with_ml = {get_key(c): c for c in port_with_ml.closed_cycles}
    trades_no_ml = {get_key(c): c for c in port_no_ml.closed_cycles}
    
    # Identify trades closed by ML Veto in the baseline run
    vetoed_keys = [k for k, c in trades_with_ml.items() if c.close_reason == "ML_VETO_CLOSE"]
    
    saved_losses = 0
    saved_losses_usd = 0.0
    killed_wins = 0
    killed_wins_usd = 0.0
    other_outcomes = []
    
    counterfactual_details = []
    
    for k in vetoed_keys:
        vetoed_trade = trades_with_ml[k]
        symbol, entry_time_str = k
        
        # Find corresponding trade in the run without ML
        cf_trade = trades_no_ml.get(k)
        if cf_trade:
            outcome = cf_trade.close_reason
            cf_profit = cf_trade.current_profit_usd
            vetoed_profit = vetoed_trade.current_profit_usd # Loss realized when vetoed
            
            # Did veto help or hurt?
            # Difference = vetoed_profit - cf_profit
            # If difference > 0: veto saved money
            # If difference < 0: veto lost money
            pnl_impact = vetoed_profit - cf_profit
            
            if cf_profit > 0:
                # Veto killed a winning trade
                killed_wins += 1
                killed_wins_usd += cf_profit - vetoed_profit # Potential profit lost
            else:
                # Veto saved or reduced a loss
                saved_losses += 1
                saved_losses_usd += abs(cf_profit) - abs(vetoed_profit) # Loss avoided
                
            counterfactual_details.append({
                "Symbol": symbol,
                "Entry_Time": entry_time_str,
                "Veto_PnL": f"${vetoed_profit:.2f}",
                "CF_PnL": f"${cf_profit:.2f}",
                "CF_Outcome": outcome,
                "Impact": f"${pnl_impact:+.2f}"
            })
        else:
            other_outcomes.append(k)
            
    df_cf = pd.DataFrame(counterfactual_details)
    
    # Generate profiling report
    report_path = Path("scratch/ml_veto_profile_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# ML Gatekeeper Veto Counterfactual Profiling Report\n\n")
        f.write(f"Analyzed trades under the optimized Break-Even settings (Activation: 1.25 ATR, Buffer: -0.05 ATR).\n\n")
        
        f.write("## Overall Performance Comparison\n\n")
        f.write("| Metric | WITH ML Veto (Baseline) | WITHOUT ML Veto (Counterfactual) | Difference |\n")
        f.write("| :--- | :--- | :--- | :--- |\n")
        f.write(f"| **Net Profit** | ${metrics_with_ml['total_profit_usd']:.2f} ({metrics_with_ml['profit_percent']:.2f}%) | ${metrics_no_ml['total_profit_usd']:.2f} ({metrics_no_ml['profit_percent']:.2f}%) | ${metrics_with_ml['total_profit_usd'] - metrics_no_ml['total_profit_usd']:+.2f} |\n")
        f.write(f"| **Win Rate** | {metrics_with_ml['win_rate']:.2f}% | {metrics_no_ml['win_rate']:.2f}% | {metrics_with_ml['win_rate'] - metrics_no_ml['win_rate']:+.2f}% |\n")
        f.write(f"| **Profit Factor** | {metrics_with_ml['profit_factor']:.2f} | {metrics_no_ml['profit_factor']:.2f} | {metrics_with_ml['profit_factor'] - metrics_no_ml['profit_factor']:+.2f} |\n")
        f.write(f"| **Max Drawdown** | {metrics_with_ml['max_drawdown_percent']:.2f}% | {metrics_no_ml['max_drawdown_percent']:.2f}% | {metrics_with_ml['max_drawdown_percent'] - metrics_no_ml['max_drawdown_percent']:+.2f}% |\n")
        f.write(f"| **Total Trades** | {metrics_with_ml['total_cycles']} | {metrics_no_ml['total_cycles']} | {metrics_with_ml['total_cycles'] - metrics_no_ml['total_cycles']} |\n\n")
        
        f.write("## ML Veto Efficacy Analysis\n")
        f.write(f"* **Total Vetoed Trades:** {len(vetoed_keys)}\n")
        f.write(f"* **Saved Losses:** {saved_losses} trades (Veto avoided a larger loss)\n")
        f.write(f"* **Killed Wins:** {killed_wins} trades (Veto accidentally cut a winning trade)\n")
        
        net_impact_usd = metrics_with_ml['total_profit_usd'] - metrics_no_ml['total_profit_usd']
        f.write(f"* **Net Financial Impact of ML Gatekeeper:** **${net_impact_usd:+.2f} USD**\n\n")
        
        if not df_cf.empty:
            f.write("### Vetoed Trades Breakdown Table\n\n")
            headers = df_cf.columns.tolist()
            f.write("| " + " | ".join(headers) + " |\n")
            f.write("| " + " | ".join(["---"] * len(headers)) + " |\n")
            for _, row in df_cf.iterrows():
                f.write("| " + " | ".join(str(row[col]) for col in headers) + " |\n")
        else:
            f.write("No trades were vetoed by the ML gatekeeper in this run.\n")
            
    print(f"\nAnalysis complete! Report written to {report_path.absolute()}")

if __name__ == '__main__':
    main()
