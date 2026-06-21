import sys
import os

if sys.version_info >= (3, 7):
    sys.stdout.reconfigure(encoding='utf-8')

log_path = r"d:\05_Quant\NOWTRAEDING\logs\audit_2026-06-15.jsonl"
if os.path.exists(log_path):
    print("Reading last 20 lines of audit_2026-06-15.jsonl:")
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        for l in lines[-20:]:
            print(l.strip())
else:
    print("Audit log not found at", log_path)
