import json
from collections import Counter

log_path = r"d:\05_Quant\NOWTRAEDING\logs\audit_2026-06-15.jsonl"

opens = []
closes = []
blocks = Counter()
ml_unsafe_scores = []
reasons = Counter()

with open(log_path, "r", encoding="utf-8") as f:
    for line in f:
        try:
            data = json.loads(line.strip())
            event = data.get("event")
            if event == "CYCLE_OPEN":
                opens.append(data)
            elif event == "CYCLE_CLOSE":
                closes.append(data)
            
            # Count blocking reasons
            action = data.get("execution_action")
            reason = data.get("reason")
            symbol = data.get("symbol")
            
            if action == "ML_BLOCKED" or (reason and "ML" in reason):
                blocks[f"ML_BLOCKED_{symbol}"] += 1
                if "Score:" in reason:
                    # Extract score
                    try:
                        score = float(reason.split("Score:")[1].split()[0])
                        ml_unsafe_scores.append((symbol, score, reason))
                    except Exception:
                        pass
            elif action == "BLOCKED" or reason:
                # Group common reasons
                if "Hourly gate" in reason:
                    blocks["Hourly gate"] += 1
                elif "HOLD:" in reason:
                    # e.g., "HOLD: Regime=TRANSITION or Pullback not exhausted" -> clean up
                    cleaned_reason = reason.replace("HOLD: ", "")
                    blocks[f"HOLD_{cleaned_reason}"] += 1
                else:
                    blocks[reason] += 1
        except Exception as e:
            pass

print("=== CYCLE OPENS ===")
for op in opens:
    print(json.dumps(op, indent=2))

print("\n=== CYCLE CLOSES ===")
for cl in closes:
    print(json.dumps(cl, indent=2))

print("\n=== TOP 20 BLOCKS/SKIPS ===")
for r, count in blocks.most_common(20):
    print(f"{r}: {count}")

print("\n=== ML SCORE EXAMPLES ===")
for sym, score, r in ml_unsafe_scores[:10]:
    print(f"{sym}: {score} -> {r}")
