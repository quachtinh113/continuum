import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from v9_continuum.backtest import V9ContinuumBacktester

def main():
    end_date = datetime(2026, 6, 18, tzinfo=timezone.utc)
    start_date = end_date - timedelta(days=365)
    
    # 10 core symbols (excluding BTCUSD and US30)
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "US100", "US500", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]
    available_symbols = []
    for s in symbols:
        if (PROJECT_ROOT / "data" / "historical" / f"{s}_M15.csv").exists():
            available_symbols.append(s)
            
    print(f"Starting Weekend Validation Backtest on {available_symbols}")
    
    scenarios = [
        {"name": "A. Baseline (No Pre-Close)", "weekend_pre_close_hour": None},
        {"name": "B. Weekend Pre-Close (21:00 UTC)", "weekend_pre_close_hour": 21},
        {"name": "C. Conservative Pre-Close (20:00 UTC)", "weekend_pre_close_hour": 20}
    ]
    
    results = {}
    portfolios = {}
    
    for sc in scenarios:
        name = sc["name"]
        close_hour = sc["weekend_pre_close_hour"]
        print(f"\n>>> Running Scenario: {name} (Hour: {close_hour})")
        
        tester = V9ContinuumBacktester(
            base_target_usd=180.0,
            risk_percent=0.15,
            weekend_pre_close_hour=close_hour
        )
        
        portfolio, metrics = tester.run(available_symbols, start_date, end_date, initial_balance=10000.0)
        results[name] = metrics
        portfolios[name] = portfolio
        
        print(f"    Net Profit      : ${metrics['total_profit_usd']:+,.2f} ({metrics['profit_percent']:+,.2f}%)")
        print(f"    Max Drawdown    : ${metrics['max_drawdown_usd']:,.2f} ({metrics['max_drawdown_percent']:.2f}%)")
        print(f"    Win Rate        : {metrics['win_rate']:.2f}%")
        print(f"    Profit Factor   : {metrics['profit_factor']}")
        print(f"    Total Trades    : {metrics['total_cycles']}")
        print(f"    Close Reasons   : {metrics['reasons']}")
        
    # Generate Markdown Report
    report_file = PROJECT_ROOT / "v9_weekend_validation_report.md"
    
    # Summary Table
    table = "| Scenario | Final Balance | Net Profit | Win Rate | Profit Factor | Max Drawdown | Trades | TP Exits | 12H ML Cuts | 24H Cuts | DD Cuts | Weekend Pre-Closes |\n"
    table += "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
    
    for name, m in results.items():
        reasons = m["reasons"]
        tp = reasons.get("TAKE_PROFIT", 0)
        ml = reasons.get("12H_ML_CUT", 0)
        hard_24 = reasons.get("24H_HARD_CUT", 0)
        dd = reasons.get("DAILY_DRAWDOWN_CUT", 0)
        w_close = reasons.get("WEEKEND_PRE_CLOSE", 0)
        
        table += (
            f"| {name} | ${m['final_balance']:,.2f} | **{m['total_profit_usd']:+,.2f} ({m['profit_percent']:+,.2f}%)** | "
            f"{m['win_rate']:.2f}% | {m['profit_factor']} | ${m['max_drawdown_usd']:,.2f} ({m['max_drawdown_percent']:.2f}%) | "
            f"{m['total_cycles']} | {tp} | {ml} | {hard_24} | {dd} | {w_close} |\n"
        )
        
    # Calculate recovery factor safely
    rf_a = results["A. Baseline (No Pre-Close)"]["total_profit_usd"] / results["A. Baseline (No Pre-Close)"]["max_drawdown_usd"] if results["A. Baseline (No Pre-Close)"]["max_drawdown_usd"] > 0 else 99.9
    rf_b = results["B. Weekend Pre-Close (21:00 UTC)"]["total_profit_usd"] / results["B. Weekend Pre-Close (21:00 UTC)"]["max_drawdown_usd"] if results["B. Weekend Pre-Close (21:00 UTC)"]["max_drawdown_usd"] > 0 else 99.9
    rf_c = results["C. Conservative Pre-Close (20:00 UTC)"]["total_profit_usd"] / results["C. Conservative Pre-Close (20:00 UTC)"]["max_drawdown_usd"] if results["C. Conservative Pre-Close (20:00 UTC)"]["max_drawdown_usd"] > 0 else 99.9

    content = f"""# V9 Continuum Weekend Validation Report

Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")} UTC
Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} (1 year)
Symbols: `{available_symbols}`

## 📊 Side-by-Side Comparison

{table}

## 🔍 Key Insights

### 1. Drawdown Reduction
- Check how much the Max Drawdown was reduced from **Scenario A** to **Scenario B** and **Scenario C**.
- Standard target is to see a reduction in drawdown without significantly hurting profits.

### 2. Profit Trade-off
- Verify that the Net Profit of **Scenario B** and **Scenario C** is within **85%** of the Baseline **Scenario A**.
- If profits drop too much, closing early might be cutting winning cycles too early.

### 3. Recovery Factor Comparison
- **Scenario A (Baseline)** Recovery Factor: {rf_a:.2f}
- **Scenario B (21:00 UTC)** Recovery Factor: {rf_b:.2f}
- **Scenario C (20:00 UTC)** Recovery Factor: {rf_c:.2f}
"""

    report_file.write_text(content, encoding="utf-8")
    print(f"\nDetailed comparison report saved to {report_file.absolute()}")

if __name__ == "__main__":
    main()
