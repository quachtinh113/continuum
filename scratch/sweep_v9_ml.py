import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from multiprocessing import Pool

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from v9_continuum.backtest import V9ContinuumBacktester

# Define worker function at module level for pickling
def run_single_backtest(args):
    target, ml_extend, ml_cut, dca_scale, ml_veto, available_symbols, start_date, end_date = args
    print(f"Starting run: Target=${target:.1f}, ML Extend={ml_extend:.2f}, ML Cut={ml_cut:.2f}")
    
    tester = V9ContinuumBacktester(
        base_target_usd=target,
        dca_multiplier_scale=dca_scale,
        ml_veto_threshold=ml_veto,
        ml_extend_threshold=ml_extend,
        ml_cut_threshold=ml_cut
    )
    portfolio, metrics = tester.run(available_symbols, start_date, end_date, initial_balance=10000.0)
    
    result = {
        "target": target,
        "ml_extend": ml_extend,
        "ml_cut": ml_cut,
        "final_balance": metrics["final_balance"],
        "net_profit": metrics["total_profit_usd"],
        "net_profit_pct": metrics["profit_percent"],
        "win_rate": metrics["win_rate"],
        "profit_factor": metrics["profit_factor"],
        "max_dd": metrics["max_drawdown_percent"],
        "trades": metrics["total_cycles"],
        "reasons": metrics["reasons"]
    }
    print(f"Finished run: Target=${target:.1f}, ML Extend={ml_extend:.2f}, ML Cut={ml_cut:.2f} | Net: ${metrics['total_profit_usd']:+,.2f}")
    return result

def run_sweep():
    # Setup parameters
    end_date = datetime(2026, 6, 18, tzinfo=timezone.utc)
    start_date = end_date - timedelta(days=365)
    
    symbols_to_test = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "US100", "US500", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]
    available_symbols = []
    for s in symbols_to_test:
        if (PROJECT_ROOT / "data" / "historical" / f"{s}_M15.csv").exists():
            available_symbols.append(s)

    # Suggesed targeted sweep parameters: 3 * 3 * 3 = 27 runs
    target_values = [180.0, 200.0, 220.0]
    ml_extend_thresholds = [0.40, 0.45, 0.50]
    ml_cut_thresholds = [0.60, 0.65, 0.70]
    
    dca_scale = 1.0
    ml_veto = 0.60
    
    tasks = []
    for target in target_values:
        for ml_extend in ml_extend_thresholds:
            for ml_cut in ml_cut_thresholds:
                tasks.append((target, ml_extend, ml_cut, dca_scale, ml_veto, available_symbols, start_date, end_date))
                
    print(f"Starting parallel ML cognitive cutoff parameters sweep ({len(tasks)} combinations on 4 CPU cores):")
    print(f"  Targets: {target_values}")
    print(f"  ML extend thresholds: {ml_extend_thresholds}")
    print(f"  ML cut thresholds: {ml_cut_thresholds}")
    
    # Run in parallel using 4 processes
    with Pool(processes=4) as pool:
        results = pool.map(run_single_backtest, tasks)

    # Sort results by Net Profit (descending)
    results.sort(key=lambda x: x["net_profit"], reverse=True)

    # Save summary report
    summary_file = PROJECT_ROOT / "v9_sweep_ml_report.md"
    
    table_rows = []
    for r in results:
        reasons = r["reasons"]
        tp = reasons.get("TAKE_PROFIT", 0)
        ml = reasons.get("12H_ML_CUT", 0)
        hard = reasons.get("24H_HARD_CUT", 0)
        dd = reasons.get("DAILY_DRAWDOWN_CUT", 0)
        
        table_rows.append(
            f"| ${r['target']:.1f} | {r['ml_extend']:.2f} | {r['ml_cut']:.2f} | ${r['final_balance']:,.2f} | **{r['net_profit']:+,.2f} ({r['net_profit_pct']:+,.2f}%)** | "
            f"{r['win_rate']:.2f}% | {r['profit_factor']} | {r['max_dd']:.2f}% | {r['trades']} | "
            f"{tp} | {ml} | {hard} | {dd} |"
        )
    
    content = f"""# V9 Continuum ML Cutoff Parameter Sweep Report

Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")} UTC
Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} (1 year)

## Configuration (Fixed Parameters)
- DCA Spacing Scale: {dca_scale:.2f}
- ML Veto Threshold: {ml_veto:.2f}

## Summary Table (Sorted by Net Profit)

| Base Target USD | ML Extend | ML Cut | Final Balance | Net Profit | Win Rate | Profit Factor | Max Drawdown | Trades | TP Exits | 12H ML Cuts | 24H Hard Cuts | Daily DD Cuts |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{"\n".join(table_rows)}

## Key Insights
1. **ML Extend & Cut Impact:** Tuning the boundaries of the ML cognitive cutoff helps avoid premature exits of winning trades under consolidation, while protecting equity from runaway trends.
"""
    summary_file.write_text(content, encoding="utf-8")
    print(f"\nSweep complete! Summary report saved to {summary_file.absolute()}")

if __name__ == "__main__":
    run_sweep()
