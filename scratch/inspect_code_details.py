import sys
import re
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

files_to_check = [
    "src/risk_engine.py",
    "v9_continuum/core/governor.py",
    "src/xgboost_gatekeeper.py",
    "v9_continuum/meta_labeling_engine.py",
    "src/portfolio_engine.py",
    "v9_continuum/layers/position.py",
    "config/settings.py",
    "src/mt5_connector.py",
    "src/signal_engine.py"
]

for filepath in files_to_check:
    p = Path(filepath)
    if not p.exists():
        print(f"File not found: {filepath}")
        continue
    print("="*80)
    print(f"FILE: {filepath}")
    print("="*80)
    content = p.read_text(encoding="utf-8")
    lines = content.splitlines()
    print(f"Total lines: {len(lines)}")
    for i, line in enumerate(lines, 1):
        if any(k in line for k in ["drawdown", "Drawdown", "LOCKED", "lot", "Lot", "confidence", "predict", "Kelly", "corr", "Corr", "breach", "Emergency"]):
            print(f"  L{i}: {line[:120]}")
