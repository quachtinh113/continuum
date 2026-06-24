import sys
import json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

def inspect_lines(log_path, start_line, end_line):
    print(f"\n==========================================")
    print(f"LINES {start_line} TO {end_line} IN: {log_path.name}")
    print(f"==========================================")
    
    with open(log_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if line_num < start_line:
                continue
            if line_num > end_line:
                break
            print(f"Line {line_num}: {line.strip()}")

if __name__ == "__main__":
    project_root = Path("d:/05_Quant/v9 Continuum")
    inspect_lines(project_root / "logs" / "audit_2026-06-23.jsonl", 180, 220)
