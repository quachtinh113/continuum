import json
import glob
import os
from collections import Counter

files = sorted(glob.glob("logs/audit_2026-08-1*.jsonl"))

print(f"Analyzing {len(files)} log files for this week (Aug 10-16):")

for fpath in files:
    filename = os.path.basename(fpath)
    events = Counter()
    close_events = []
    open_events = []
    veto_events = Counter()
    
    with open(fpath, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line.strip())
                evt = data.get("event") or data.get("severity") or "INFO"
                events[evt] += 1
                
                if evt == "CYCLE_CLOSE":
                    close_events.append(data)
                elif evt == "CYCLE_OPEN":
                    open_events.append(data)
                if "VETOED" in str(data.get("risk_decision")) or "BLOCKED" in str(data.get("execution_action")):
                    reason = data.get("reason", "Unknown block")
                    veto_events[reason] += 1
            except Exception:
                pass
                
    print(f"\n=================== {filename} ===================")
    print("Event distribution:")
    for k, v in events.items():
        print(f"  {k:<20}: {v}")
    if open_events:
        print(f"\nCYCLE_OPEN ({len(open_events)}):")
        for o in open_events:
            print(f"  [{o.get('timestamp')}] {o.get('symbol')} {o.get('direction')} @ {o.get('price') or o.get('entry_price')} lot={o.get('lot')}")
    if close_events:
        print(f"\nCYCLE_CLOSE ({len(close_events)}):")
        for c in close_events:
            print(f"  [{c.get('timestamp')}] {c.get('symbol')} {c.get('direction')} @ {c.get('price')} reason={c.get('reason')}")
    if veto_events:
        print("\nRisk Vetoes / Blocks:")
        for r, cnt in veto_events.items():
            print(f"  {r}: {cnt}")
