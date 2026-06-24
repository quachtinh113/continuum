import json
from pathlib import Path
from collections import Counter

def inspect_events(log_path):
    print(f"\n==========================================")
    print(f"INSPECTING: {log_path.name}")
    print(f"==========================================")
    
    if not log_path.exists():
        print("File does not exist.")
        return
        
    error_events = []
    unknown_events = []
    other_events = {}
    
    with open(log_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                event = data.get("event", "UNKNOWN")
                
                if event == "ERROR" and len(error_events) < 5:
                    error_events.append((line_num, data))
                elif event == "UNKNOWN" and len(unknown_events) < 5:
                    unknown_events.append((line_num, data))
                elif event not in ["ERROR", "UNKNOWN"] and event not in other_events:
                    other_events[event] = (line_num, data)
            except Exception as e:
                pass
                
    print("--- SAMPLE ERROR EVENTS ---")
    for num, data in error_events:
        print(f"Line {num}: {json.dumps(data, indent=2)}")
        
    print("\n--- SAMPLE UNKNOWN EVENTS ---")
    for num, data in unknown_events:
        print(f"Line {num}: {json.dumps(data, indent=2)}")
        
    print("\n--- SAMPLE OTHER EVENTS ---")
    for ev, (num, data) in other_events.items():
        print(f"Event '{ev}' (Line {num}): {json.dumps(data, indent=2)}")

if __name__ == "__main__":
    project_root = Path("d:/05_Quant/v9 Continuum")
    inspect_events(project_root / "logs" / "audit_2026-06-24.jsonl")
