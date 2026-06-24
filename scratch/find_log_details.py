import sys
import json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

def find_details(log_path):
    print(f"\n==========================================")
    print(f"OVERNIGHT LOG SEQUENCE FOR: {log_path.name}")
    print(f"==========================================")
    
    if not log_path.exists():
        print("File does not exist.")
        return
        
    with open(log_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if line_num < 12050:
                continue
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                event = data.get("event")
                reason = data.get("reason", "")
                execution_action = data.get("execution_action", "")
                
                # Filter out the repeating USDCHF vetoed logs when locked
                if "System status is LOCKED" in reason and "USDCHF" in data.get("symbol", ""):
                    continue
                    
                print(f"Line {line_num} [{data.get('timestamp')}]: event={event} | symbol={data.get('symbol')} | signal={data.get('signal')} | risk={data.get('risk_decision')} | action={execution_action} | reason={reason} | msg={data.get('message')}")
            except Exception as e:
                print(f"Line {line_num} parse error: {e} | Raw: {line[:100]}")

if __name__ == "__main__":
    project_root = Path("d:/05_Quant/v9 Continuum")
    find_details(project_root / "logs" / "audit_2026-06-24.jsonl")
