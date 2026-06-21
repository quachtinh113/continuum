import json

log_path = r"d:\05_Quant\NOWTRAEDING\logs\audit_2026-06-15.jsonl"
ticket = 4216042993
ticket_str = str(ticket)

with open(log_path, "r", encoding="utf-8") as f:
    for line in f:
        if ticket_str in line or "US100" in line:
            # Let's parse and print if relevant
            try:
                data = json.loads(line.strip())
                # If it's cycle open/close or has ticket or event:
                if any(x in str(data) for x in ["CYCLE_OPEN", "CYCLE_CLOSE", ticket_str, "ERROR", "WARNING"]):
                    print(json.dumps(data))
            except Exception:
                pass
