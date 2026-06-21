import os
import sys

if sys.version_info >= (3, 7):
    sys.stdout.reconfigure(encoding='utf-8')

log_bot = r"C:\Users\Pro Trader\.gemini\antigravity-ide\brain\ec48749c-4956-419a-b50e-b869ac13ad38\.system_generated\tasks\task-306.log"
log_audit = r"d:\05_Quant\NOWTRAEDING\logs\audit_2026-06-15.jsonl"

for name, path in [("bot log", log_bot), ("audit log", log_audit)]:
    if os.path.exists(path):
        print(f"--- Searching in {name} ---")
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "42160" in line or "USTEC" in line or "42180" in line:
                    print(line.strip())
