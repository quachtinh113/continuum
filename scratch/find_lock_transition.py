import json
from pathlib import Path

def find_transition(log_path):
    print(f"Scanning transition in: {log_path.name}")
    if not log_path.exists():
        print("File does not exist.")
        return
        
    lines = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                lines.append(line.strip())
                
    lock_line_idx = -1
    for idx, line in enumerate(lines):
        if idx < 12050:
            continue
        try:
            data = json.loads(line)
            reason = data.get("reason", "")
            if "LOCKED by global drawdown limit" in reason:
                lock_line_idx = idx
                break
        except Exception:
            pass
            
    if lock_line_idx == -1:
        print("No 'LOCKED by global drawdown limit' found after line 12050.")
        return
        
    print(f"\n--- FOUND FIRST LOCK AT LINE {lock_line_idx + 1} ---")
    start = max(12050, lock_line_idx - 10)
    end = min(len(lines), lock_line_idx + 10)
    
    for i in range(start, end):
        try:
            data = json.loads(lines[i])
            print(f"Line {i+1} [{data.get('timestamp')}]: event={data.get('event')} | symbol={data.get('symbol')} | signal={data.get('signal')} | risk={data.get('risk_decision')} | action={data.get('execution_action')} | reason={data.get('reason')} | msg={data.get('message')}")
        except Exception as e:
            print(f"Line {i+1} parse error: {e} | Raw: {lines[i][:100]}")

if __name__ == "__main__":
    project_root = Path("d:/05_Quant/v9 Continuum")
    find_transition(project_root / "logs" / "audit_2026-06-24.jsonl")
