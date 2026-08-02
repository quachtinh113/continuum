import json
import glob

def main():
    log_files = sorted(glob.glob("logs/audit_2026-07-31.jsonl"))
    if not log_files:
        print("No log files found")
        return

    with open(log_files[0], "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            evt = data.get("event", "")
            if evt == "CYCLE_CLOSE":
                print(f"--- Event: {evt} ---")
                print(json.dumps(data, indent=2))
                break

if __name__ == "__main__":
    main()
