import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding='utf-8')

from src.backtest_engine import BacktestEngine
from config import settings

data_dir = Path("data/historical")
csv_files = list(data_dir.glob("*_M15.csv"))
symbols = [f.name.replace("_M15.csv", "") for f in csv_files]

end_date = datetime(2026, 6, 11, tzinfo=timezone.utc)
start_date = end_date - timedelta(days=180)

print(f"Sweeping ML Gatekeeper thresholds across 6-month historical dataset ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})...\n")

print(f"{'Threshold':<10} | {'Trades':<8} | {'Win Rate (%)':<12} | {'Profit ($)':<12} | {'Max DD (%)':<12} | {'Sharpe':<8}")
print("-" * 75)

# Benchmark: No ML
settings.ML_GATEKEEPER_ACTIVE = False
engine_none = BacktestEngine(data_dir=str(data_dir))
_, m_none = engine_none.run_backtest(symbols=symbols, start_date=start_date, end_date=end_date, initial_balance=10000.0)
print(f"{'NO ML':<10} | {m_none.get('total_cycles', 0):<8} | {m_none.get('win_rate', 0):<12.2f} | ${m_none.get('total_profit_usd', 0):<11.2f} | {m_none.get('max_drawdown_percent', 0):<12.2f} | {m_none.get('sharpe_ratio', 0):<8.2f}")

# Active ML at different thresholds
settings.ML_GATEKEEPER_ACTIVE = True
for thresh in [0.85, 0.80, 0.75, 0.70, 0.65]:
    settings.ML_ENTRY_SAFE_THRESHOLD = thresh
    engine = BacktestEngine(data_dir=str(data_dir))
    _, m = engine.run_backtest(symbols=symbols, start_date=start_date, end_date=end_date, initial_balance=10000.0)
    print(f"{thresh:<10.2f} | {m.get('total_cycles', 0):<8} | {m.get('win_rate', 0):<12.2f} | ${m.get('total_profit_usd', 0):<11.2f} | {m.get('max_drawdown_percent', 0):<12.2f} | {m.get('sharpe_ratio', 0):<8.2f}")
