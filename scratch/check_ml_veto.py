import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
p = Path("logs/ml_veto_audit.jsonl")

if p.exists():
    lines = p.read_text(encoding="utf-8").splitlines()
    print(f"Total ML Veto Audit entries: {len(lines)}")
    print("Last 10 entries:")
    for line in lines[-10:]:
        print(line)
else:
    print("ml_veto_audit.jsonl does not exist")
