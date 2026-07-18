import json
from pathlib import Path

def find_startups(log_path):
    print(f"\n==========================================")
    print(f"STARTUP SEARCH FOR: {log_path.name}")
    print(f"==========================================")
    
    if not log_path.exists():
        print("File does not exist.")
        return
        
    with open(log_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                message = data.get("message", "")
                if "Initialized" in message or "Daily reset" in message or "Recovered" in message:
                    print(f"Line {line_num} [{data.get('timestamp')}]: {message}")
            except Exception as e:
                pass

if __name__ == "__main__":
    project_root = Path("d:/05_Quant/v9 Continuum")
    find_startups(project_root / "logs" / "audit_2026-06-30.jsonl")
    find_startups(project_root / "logs" / "audit_2026-07-01.jsonl")
