import json
import sys

# Reconfigure stdout to use UTF-8 to handle Unicode characters on Windows console
if sys.version_info >= (3, 7):
    sys.stdout.reconfigure(encoding='utf-8')

log_path = r"d:\05_Quant\NOWTRAEDING\logs\audit_2026-06-15.jsonl"

print("Tracing US100 cycle events:")
with open(log_path, "r", encoding="utf-8") as f:
    for line in f:
        try:
            data = json.loads(line.strip())
            symbol = data.get("symbol")
            if symbol == "US100":
                # Let's filter logs that contain indicator values or decisions
                event = data.get("event")
                reason = data.get("reason")
                action = data.get("execution_action")
                timestamp = data.get("timestamp")
                
                # Check if it has ATR
                atr = data.get("ATR")
                pnl = data.get("profit_usd")
                
                # If there's an event or special decision
                if event in ["CYCLE_OPEN", "CYCLE_CLOSE"] or action in ["OPEN_BUY", "OPEN_SELL", "ML_BLOCKED"] or "BE Activated" in str(data) or "Break-Even" in str(reason):
                    print(f"{timestamp} | EVENT: {event or action} | Reason: {reason} | PnL: {pnl} | ATR: {atr}")
                elif "BE" in str(reason) or "BE" in str(data.get("message", "")):
                    print(f"{timestamp} | MSG: {data}")
        except Exception as e:
            pass
