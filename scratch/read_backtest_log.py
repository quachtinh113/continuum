import os
import sys
from pathlib import Path

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    tasks_dir = r"C:\Users\Pro Trader\.gemini\antigravity-ide\brain\9e032512-c6a8-4f3a-8a89-3d45542de44b\.system_generated\tasks"
    log_files = list(Path(tasks_dir).glob("*1248*.log"))
    if not log_files:
        print(f"No log file matching *1248* in {tasks_dir}")
        return
    log_path = log_files[0]
    print(f"Reading log file: {log_path}")
        
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
        print(f"Total log lines: {len(lines)}")
        for line in lines[-25:]:
            print(line.strip())

if __name__ == '__main__':
    main()
