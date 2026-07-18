import json
import argparse
from datetime import datetime
from pathlib import Path
from collections import Counter

import sys

def parse_args():
    parser = argparse.ArgumentParser(description="Optimize trading log analysis and compress token size.")
    parser.add_argument("--file", type=str, required=True, help="Path to the jsonl log file.")
    parser.add_argument("--event", type=str, default=None, help="Filter specifically by event type (e.g., CYCLE_OPEN, CYCLE_CLOSE, DCA_OPEN).")
    parser.add_argument("--errors", action="store_true", help="Filter only ERROR or WARNING events.")
    parser.add_argument("--summary", action="store_true", help="Print a summarized statistical breakdown of the log session.")
    parser.add_argument("--tail", type=int, default=None, help="Only print the last N matching lines.")
    return parser.parse_args()

def analyze_logs():
    sys.stdout.reconfigure(encoding='utf-8')
    args = parse_args()
    log_path = Path(args.file)
    if not log_path.exists():
        print(f"Error: Log file {args.file} not found.")
        return

    events = []
    errors_warnings = []
    event_counts = Counter()
    veto_reasons = Counter()
    total_lines = 0

    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            total_lines += 1
            try:
                data = json.loads(line.strip())
                # Track event count
                event_type = data.get("event") or data.get("severity") or "INFO"
                event_counts[event_type] += 1
                
                # Capture veto reasons
                if "VETOED" in str(data.get("risk_decision")) or "BLOCKED" in str(data.get("execution_action")):
                    reason = data.get("reason", "Unknown block")
                    veto_reasons[reason] += 1

                # Filter logic
                match = True
                if args.errors and data.get("severity") not in ["ERROR", "WARNING"] and data.get("event") != "ERROR":
                    match = False
                if args.event and data.get("event") != args.event:
                    match = False

                if match:
                    events.append(data)
            except Exception:
                pass

    if args.summary:
        print("============================================================")
        print(f"📊 SUMMARY BREAKDOWN FOR: {log_path.name}")
        print("============================================================")
        print(f"Total Raw Lines Analyzed │ {total_lines}")
        print("\n[Event / Severity Distribution]")
        for evt, count in event_counts.items():
            print(f"  {evt:<22} │ {count}")
            
        if veto_reasons:
            print("\n[Risk Engine Blocks / Vetoes]")
            for reason, count in veto_reasons.items():
                print(f"  {reason:<45} │ {count}")
        print("============================================================\n")

    # Handle print output with optional tail
    output_events = events[-args.tail:] if args.tail else events
    if output_events and not (args.summary and not args.event and not args.errors):
        print(f"Showing {len(output_events)} matching log entries:")
        for ev in output_events:
            # Condense format to save token space
            timestamp = ev.get("timestamp", "")
            if len(timestamp) > 19:
                timestamp = timestamp[11:19] # Only show HH:MM:SS for brevity
            
            symbol = ev.get("symbol", "")
            event_name = ev.get("event") or ev.get("severity") or "INFO"
            msg = ev.get("message") or ev.get("reason") or ""
            
            lot_val = ev.get('lot') or ev.get('lot_size') or 0.0
            price_val = ev.get('price') or ev.get('entry_price') or ev.get('dca_price') or 0.0
            if event_name == "CYCLE_OPEN":
                print(f"[{timestamp}] 🟩 OPEN  │ {symbol:<7} │ Dir: {ev.get('direction')} │ Lot: {lot_val:.3f} │ Px: {price_val}")
            elif event_name == "CYCLE_CLOSE":
                print(f"[{timestamp}] 🟥 CLOSE │ {symbol:<7} │ Dir: {ev.get('direction')} │ Exit: {price_val} │ Reason: {ev.get('reason')}")
            elif event_name == "DCA_OPEN":
                print(f"[{timestamp}] 🟨 DCA   │ {symbol:<7} │ Layer: {ev.get('layer')} │ Lot: {lot_val:.3f} │ Px: {price_val}")
            elif event_name in ["ERROR", "WARNING"]:
                print(f"[{timestamp}] ❌ {event_name:<5} │ {msg}")
            else:
                if msg:
                    print(f"[{timestamp}] ℹ️  {event_name:<5} │ {symbol:<7} │ {msg}")

if __name__ == "__main__":
    analyze_logs()
