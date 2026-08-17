import json
from pathlib import Path
from datetime import datetime

def main():
    log_paths = [Path("logs/audit_2026-08-06.jsonl"), Path("logs/audit_2026-08-07.jsonl")]
    for log_path in log_paths:
        if not log_path.exists():
            continue
        print(f"\n--- {log_path.name} Vetoes or Approvals for XAUUSD/US100 post-calibration ---")
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    if data.get("symbol") in ["XAUUSD", "US100"]:
                        ts_str = data.get("timestamp")
                        ts = datetime.strptime(ts_str[:19], "%Y-%m-%dT%H:%M:%S")
                        if log_path.name == "audit_2026-08-06.jsonl" and ts < datetime(2026, 8, 6, 10, 13, 0):
                            continue
                        
                        risk = data.get("risk_decision") or data.get("execution_action")
                        # Print only if it generated a decision (meaning sig_val != HOLD)
                        if risk:
                            print(f"[{ts_str}] Symbol: {data.get('symbol')} | Signal: {data.get('signal')} | Risk: {risk} | Reason: {data.get('reason')}")
                except Exception:
                    pass

if __name__ == '__main__':
    main()
