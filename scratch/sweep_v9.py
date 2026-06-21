import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from v9_continuum.backtest import V9ContinuumBacktester

def run_sweep():
    # Setup parameters
    end_date = datetime(2026, 6, 18, tzinfo=timezone.utc)
    start_date = end_date - timedelta(days=365)
    
    symbols_to_test = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "US100", "US500", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]
    available_symbols = []
    for s in symbols_to_test:
        if (PROJECT_ROOT / "data" / "historical" / f"{s}_M15.csv").exists():
            available_symbols.append(s)

    target_values = [100.0, 120.0, 150.0, 180.0, 200.0]
    dca_scales = [1.0, 1.2, 1.5, 1.8]
    ml_veto_thresholds = [0.5, 0.55, 0.6, 0.65]
    
    print("Starting multi-dimensional parameter sweep:")
    print(f"  Targets: {target_values}")
    print(f"  DCA scales: {dca_scales}")
    print(f"  ML vetoes: {ml_veto_thresholds}")
    print(f"Symbols: {available_symbols}")
    
    results = []
    total_runs = len(target_values) * len(dca_scales) * len(ml_veto_thresholds)
    run_idx = 0
    
    for target in target_values:
        for dca_scale in dca_scales:
            for ml_veto in ml_veto_thresholds:
                run_idx += 1
                print(f"\n[{run_idx}/{total_runs}] Running backtest: Target=${target:.1f}, DCA Scale={dca_scale:.2f}, ML Veto={ml_veto:.2f}")
                tester = V9ContinuumBacktester(
                    base_target_usd=target,
                    dca_multiplier_scale=dca_scale,
                    ml_veto_threshold=ml_veto
                )
                portfolio, metrics = tester.run(available_symbols, start_date, end_date, initial_balance=10000.0)
                
                results.append({
                    "target": target,
                    "dca_scale": dca_scale,
                    "ml_veto": ml_veto,
                    "final_balance": metrics["final_balance"],
                    "net_profit": metrics["total_profit_usd"],
                    "net_profit_pct": metrics["profit_percent"],
                    "win_rate": metrics["win_rate"],
                    "profit_factor": metrics["profit_factor"],
                    "max_dd": metrics["max_drawdown_percent"],
                    "trades": metrics["total_cycles"],
                    "reasons": metrics["reasons"]
                })
                
                print(f"  Net: ${metrics['total_profit_usd']:+,.2f} ({metrics['profit_percent']:+,.2f}%) | DD: {metrics['max_drawdown_percent']:.2f}% | PF: {metrics['profit_factor']} | Win: {metrics['win_rate']:.2f}%")

    # Sort results by Net Profit (descending)
    results.sort(key=lambda x: x["net_profit"], reverse=True)

    # Save summary report
    summary_file = PROJECT_ROOT / "v9_sweep_report.md"
    
    table_rows = []
    for r in results:
        reasons = r["reasons"]
        tp = reasons.get("TAKE_PROFIT", 0)
        ml = reasons.get("12H_ML_CUT", 0)
        hard = reasons.get("24H_HARD_CUT", 0)
        dd = reasons.get("DAILY_DRAWDOWN_CUT", 0)
        
        table_rows.append(
            f"| ${r['target']:.1f} | {r['dca_scale']:.2f} | {r['ml_veto']:.2f} | ${r['final_balance']:,.2f} | **{r['net_profit']:+,.2f} ({r['net_profit_pct']:+,.2f}%)** | "
            f"{r['win_rate']:.2f}% | {r['profit_factor']} | {r['max_dd']:.2f}% | {r['trades']} | "
            f"{tp} | {ml} | {hard} | {dd} |"
        )
    
    content = f"""# V9 Continuum Parameter Sweep Optimization Report

Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")} UTC
Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} (1 year)

## Summary Table (Sorted by Net Profit)

| Base Target USD | DCA Scale | ML Veto | Final Balance | Net Profit | Win Rate | Profit Factor | Max Drawdown | Trades | TP Exits | 12H ML Cuts | 24H Hard Cuts | Daily DD Cuts |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{"\n".join(table_rows)}

## Key Insights
1. **Profitability Sweet Spot:** Look for the target that balances the win rate and the average payout per trade to yield positive net profit.
2. **Drawdown Relationship:** Larger targets might lead to longer holding times, increasing average DCA layers and drawdown risk.
"""
    summary_file.write_text(content, encoding="utf-8")
    print(f"\nSweep complete! Summary report saved to {summary_file.absolute()}")

if __name__ == "__main__":
    run_sweep()
