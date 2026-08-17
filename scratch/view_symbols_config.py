import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

p = Path("config/symbols.py")
if p.exists():
    print(p.read_text(encoding="utf-8"))
else:
    print("config/symbols.py not found.")
