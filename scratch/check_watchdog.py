import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
watchdog_path = Path("logs/watchdog.log")

if watchdog_path.exists():
    lines = watchdog_path.read_text(encoding="utf-8").splitlines()
    print("Last 20 lines of watchdog.log:")
    for line in lines[-20:]:
        print(line)
else:
    print("watchdog.log does not exist.")
