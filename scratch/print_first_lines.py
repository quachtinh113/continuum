import json
from pathlib import Path

def print_first_lines(log_path, num_lines=10):
    print(f"\n==========================================")
    print(f"FIRST {num_lines} LINES OF: {log_path.name}")
    print(f"==========================================")
    
    if not log_path.exists():
        print("File does not exist.")
        return
        
    with open(log_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if i > num_lines:
                break
            print(f"Line {i}: {line.strip()}")

if __name__ == "__main__":
    project_root = Path("d:/05_Quant/v9 Continuum")
    print_first_lines(project_root / "logs" / "audit_2026-06-23.jsonl")
    print_first_lines(project_root / "logs" / "audit_2026-06-24.jsonl")
