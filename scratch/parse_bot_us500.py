import os
import sys

if sys.version_info >= (3, 7):
    sys.stdout.reconfigure(encoding='utf-8')

log_path = r"C:\Users\Pro Trader\.gemini\antigravity-ide\brain\ec48749c-4956-419a-b50e-b869ac13ad38\.system_generated\tasks\task-306.log"
if not os.path.exists(log_path):
    log_path = log_path.replace("\\", "/")

if os.path.exists(log_path):
    print("Found bot log. Filtering for US500 events:")
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "US500" in line:
                if any(x in line for x in ["CYCLE_OPEN", "CYCLE_CLOSE", "ORDER FILLED", "BE Activated", "Stoploss", "Take profit", "Veto", "ML_VETO_CLOSE", "SL Modified", "Score"]):
                    print(line.strip())
else:
    print("Bot log not found at", log_path)
