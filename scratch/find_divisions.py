import re
from pathlib import Path

def find_divisions():
    content = Path("v9_continuum/main.py").read_text(encoding="utf-8")
    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        if "/" in line and not line.strip().startswith("#") and not line.strip().startswith('"""'):
            if not "http" in line and not "Global\\" in line and not "logs/" in line:
                print(f"Line {i:4d}: {line.strip()}")

if __name__ == "__main__":
    find_divisions()
