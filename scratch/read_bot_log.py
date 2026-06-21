import os
import sys

if sys.version_info >= (3, 7):
    sys.stdout.reconfigure(encoding='utf-8')

log_path = r"C:\Users\Pro Trader\.gemini\antigravity-ide\brain\ec48749c-4956-419a-b50e-b869ac13ad38\.system_generated\tasks\task-560.log"
if not os.path.exists(log_path):
    log_path = log_path.replace("\\", "/")

if os.path.exists(log_path):
    print("Reading task-560.log:")
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            print(line.strip())
else:
    print("Bot log not found at", log_path)
