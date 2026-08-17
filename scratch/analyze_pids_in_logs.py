import json
from pathlib import Path
from collections import Counter

def main():
    log_dir = Path("logs")
    for log_path in sorted(log_dir.glob("audit_2026-08-*.jsonl")):
        pids = Counter()
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    pid = data.get("pid") or "None"
                    pids[pid] += 1
                except Exception:
                    pass
        print(f"File: {log_path.name} | PIDs writing: {dict(pids)}")

if __name__ == '__main__':
    main()
