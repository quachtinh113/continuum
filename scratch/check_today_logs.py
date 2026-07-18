import json
import sys
from pathlib import Path

def print_breach_details():
    sys.stdout.reconfigure(encoding='utf-8')
    log_path = Path("d:/05_Quant/v9 Continuum/logs/audit_2026-06-30.jsonl")
    if not log_path.exists():
        print("Log file not found.")
        return

    with open(log_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            if idx in [343, 344]:
                print(f"Line {idx}: {line.strip()}")

if __name__ == "__main__":
    print_breach_details()
