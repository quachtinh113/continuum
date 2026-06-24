import json
from pathlib import Path

def search_drawdowns(log_path):
    print(f"Searching: {log_path.name}")
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
                event = data.get("event", "")
                if "Drawdown" in message or "Breached" in message or event == "ERROR":
                    print(f"Line {line_num} [{data.get('timestamp')}]: {json.dumps(data)}")
            except Exception:
                pass

if __name__ == "__main__":
    project_root = Path("d:/05_Quant/v9 Continuum")
    search_drawdowns(project_root / "logs" / "audit_2026-06-24.jsonl")
