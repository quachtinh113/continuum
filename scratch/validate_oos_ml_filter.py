import sys
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding='utf-8')

from src.backtest_engine import BacktestEngine
from config import settings

print("="*80)
print("OUT-OF-SAMPLE (OOS) BACKTEST VALIDATION FOR FIXED ML GATEKEEPER")
print("="*80)

# Check historical data directory
data_dir = Path("data/historical")
if not data_dir.exists():
    print(f"Data dir {data_dir} does not exist!")
    sys.exit(1)

# Available historical CSV files
csv_files = list(data_dir.glob("*_M15.csv"))
symbols = [f.name.replace("_M15.csv", "") for f in csv_files]
print(f"Available symbols in data/historical: {symbols}")

# Define test date range
end_date = datetime(2026, 6, 11, tzinfo=timezone.utc)
start_date = end_date - timedelta(days=180)

# 1. RUN BACKTEST WITHOUT ML GATEKEEPER
print("\n[1/2] Running Backtest WITHOUT ML Gatekeeper...")
settings.ML_GATEKEEPER_ACTIVE = False
engine_no_ml = BacktestEngine(data_dir=str(data_dir))
port_no_ml, metrics_no_ml = engine_no_ml.run_backtest(
    symbols=symbols,
    start_date=start_date,
    end_date=end_date,
    initial_balance=10000.0,
    no_time_stop=False
)

# 2. RUN BACKTEST WITH FIXED ML GATEKEEPER
print("\n[2/2] Running Backtest WITH FIXED ML Gatekeeper...")
settings.ML_GATEKEEPER_ACTIVE = True
engine_ml = BacktestEngine(data_dir=str(data_dir))
port_ml, metrics_ml = engine_ml.run_backtest(
    symbols=symbols,
    start_date=start_date,
    end_date=end_date,
    initial_balance=10000.0,
    no_time_stop=False
)

# Extract metrics
wr_before = metrics_no_ml.get("win_rate", 0.0)
wr_after = metrics_ml.get("win_rate", 0.0)

dd_before = metrics_no_ml.get("max_drawdown_percent", 0.0)
dd_after = metrics_ml.get("max_drawdown_percent", 0.0)
dd_reduction = ((dd_before - dd_after) / dd_before * 100.0) if dd_before > 0 else 0.0

sharpe_before = metrics_no_ml.get("sharpe_ratio", 0.0)
sharpe_after = metrics_ml.get("sharpe_ratio", 0.0)

print("\n" + "="*80)
print("OOS VALIDATION SUMMARY RESULTS (6-MONTH HISTORY)")
print("="*80)
print(f"Metric                       │ BEFORE ML Filter │ AFTER Fixed ML Filter │ Improvement")
print(f"─────────────────────────────┼──────────────────┼───────────────────────┼────────────")
print(f"Win Rate (%)                 │ {wr_before:16.2f}% │ {wr_after:21.2f}% │ +{wr_after - wr_before:+.2f}%")
print(f"Max Drawdown (%)             │ {dd_before:16.2f}% │ {dd_after:21.2f}% │ -{dd_reduction:.2f}% (DD Reduction)")
print(f"Sharpe Ratio                 │ {sharpe_before:16.2f}  │ {sharpe_after:21.2f}  │ {sharpe_after - sharpe_before:+.2f}")
print(f"Total Profit ($)             │ ${metrics_no_ml.get('total_profit_usd', 0):15.2f} │ ${metrics_ml.get('total_profit_usd', 0):20.2f} │ ${metrics_ml.get('total_profit_usd', 0) - metrics_no_ml.get('total_profit_usd', 0):+.2f}")
print(f"Total Trades                 │ {metrics_no_ml.get('total_cycles', 0):16d} │ {metrics_ml.get('total_cycles', 0):21d} │ {metrics_ml.get('total_cycles', 0) - metrics_no_ml.get('total_cycles', 0):+d} (Filtered)")
print("="*80)
