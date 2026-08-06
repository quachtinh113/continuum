import os
import sys

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    log_path = r"C:\Users\Pro Trader\.gemini\antigravity-ide\brain\9e032512-c6a8-4f3a-8a89-3d45542de44b\.system_generated\tasks\task-966.log"
    if not os.path.exists(log_path):
        print(f"Log file not found at: {log_path}")
        return
        
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
        print(f"--- Log Last 20 lines ({len(lines)} total) ---")
        for line in lines[-20:]:
            print(line.strip())

if __name__ == '__main__':
    main()
