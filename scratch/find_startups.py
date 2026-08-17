import json
from pathlib import Path
from datetime import datetime

def main():
    log_paths = [Path("logs/audit_2026-08-06.jsonl"), Path("logs/audit_2026-08-07.jsonl")]
    for log_path in log_paths:
        if not log_path.exists():
            continue
        print(f"\n--- {log_path.name} CYCLE_OPEN or CYCLE_CLOSE post-calibration ---")
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    if data.get("event") in ["CYCLE_OPEN", "CYCLE_CLOSE"]:
                        ts_str = data.get("timestamp")
                        ts = datetime.strptime(ts_str[:19], "%Y-%m-%dT%H:%M:%S")
                        if log_path.name == "audit_2026-08-06.jsonl" and ts < datetime(2026, 8, 6, 10, 13, 0):
                            continue
                        print(line.strip())
                except Exception:
                    pass

if __name__ == '__main__':
    main()
