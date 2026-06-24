import json
from pathlib import Path

def search_keywords(log_path, keywords):
    print(f"\n==========================================")
    print(f"KEYWORD SEARCH FOR: {log_path.name}")
    print(f"==========================================")
    
    if not log_path.exists():
        print("File does not exist.")
        return
        
    found_count = 0
    with open(log_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                # Check all string values in data for keywords
                line_str = json.dumps(data).lower()
                if any(kw.lower() in line_str for kw in keywords):
                    print(f"Line {line_num} [{data.get('timestamp')}]: {json.dumps(data)}")
                    found_count += 1
                    if found_count >= 50:
                        print("Truncating search results after 50 matches.")
                        break
            except Exception as e:
                pass

if __name__ == "__main__":
    project_root = Path("d:/05_Quant/v9 Continuum")
    search_keywords(project_root / "logs" / "audit_2026-06-23.jsonl", ["reset", "init", "recover", "balance", "close_all_positions"])
    search_keywords(project_root / "logs" / "audit_2026-06-24.jsonl", ["reset", "init", "recover", "balance", "close_all_positions"])
