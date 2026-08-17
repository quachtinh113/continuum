import json
from pathlib import Path

def main():
    log_path = Path("logs/audit_2026-08-06.jsonl")
    with open(log_path, "r", encoding="utf-8") as f:
        for _ in range(5):
            line = f.readline()
            if not line:
                break
            print(json.loads(line.strip()))

if __name__ == '__main__':
    main()
