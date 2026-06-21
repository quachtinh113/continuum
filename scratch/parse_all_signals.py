import json
import sys
from collections import Counter

if sys.version_info >= (3, 7):
    sys.stdout.reconfigure(encoding='utf-8')

log_path = r"d:\05_Quant\NOWTRAEDING\logs\audit_2026-06-15.jsonl"

signals_summary = {}
ml_vetoes = []
other_blocks = []
approved_entries = []

with open(log_path, "r", encoding="utf-8") as f:
    for line in f:
        try:
            data = json.loads(line.strip())
            event = data.get("event")
            symbol = data.get("symbol")
            if not symbol:
                continue
                
            timestamp = data.get("timestamp")
            signal = data.get("signal")
            risk_decision = data.get("risk_decision")
            action = data.get("execution_action")
            reason = data.get("reason")
            
            if signal in ["BUY", "SELL"]:
                if risk_decision == "APPROVED":
                    approved_entries.append((timestamp, symbol, signal, reason))
                elif action == "ML_BLOCKED" or (reason and "ML" in reason):
                    ml_vetoes.append((timestamp, symbol, signal, reason))
                else:
                    other_blocks.append((timestamp, symbol, signal, reason))
            
            # Count signals per symbol
            if symbol not in signals_summary:
                signals_summary[symbol] = Counter()
            signals_summary[symbol][signal] += 1
            
        except Exception:
            pass

print("=== SIGNAL COUNTS PER SYMBOL ===")
for sym, counts in signals_summary.items():
    print(f"{sym}: {dict(counts)}")

print("\n=== APPROVED ENTRIES ===")
for ts, sym, sig, r in approved_entries:
    print(f"{ts} | {sym} | {sig} | {r}")

print("\n=== ML VETOED ENTRIES (First 20) ===")
for ts, sym, sig, r in ml_vetoes[:20]:
    print(f"{ts} | {sym} | {sig} | {r}")
print(f"Total ML Vetoes: {len(ml_vetoes)}")

print("\n=== OTHER BLOCKED/SKIPPED ENTRIES (First 20) ===")
for ts, sym, sig, r in other_blocks[:20]:
    print(f"{ts} | {sym} | {sig} | {r}")
print(f"Total Other Blocks: {len(other_blocks)}")
