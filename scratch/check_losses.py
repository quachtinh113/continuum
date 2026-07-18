import json
import sys
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

def analyze_day(log_file):
    print(f"\n==========================================")
    print(f"ANALYZING LOG FILE: {log_file.name}")
    print(f"==========================================")
    
    if not log_file.exists():
        print("Log file does not exist.")
        return
        
    breach_line = None
    breach_time = None
    breach_msg = None
    
    # First, find the first drawdown breach
    with open(log_file, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            try:
                data = json.loads(line)
                msg = data.get("message", "")
                if "Drawdown Limit Breached" in msg:
                    breach_line = idx
                    breach_time = data.get("timestamp")
                    breach_msg = msg
                    break
            except Exception:
                pass
                
    if not breach_line:
        print("No Drawdown Limit Breach found in this log.")
        return
        
    print(f"Breach detected at Line {breach_line} [{breach_time}]:")
    print(f"  {breach_msg}")
    
    # Now, find all CYCLE_OPEN, DCA_OPEN, DCA_ADD events before this breach
    positions = {}
    with open(log_file, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            if idx >= breach_line:
                break
            try:
                data = json.loads(line)
                event = data.get("event")
                symbol = data.get("symbol")
                if event in ["CYCLE_OPEN", "DCA_OPEN", "DCA_ADD", "CYCLE_CLOSE"]:
                    if event == "CYCLE_OPEN":
                        positions[symbol] = {
                            "entry_time": data.get("timestamp"),
                            "direction": data.get("direction"),
                            "price": data.get("price"),
                            "lot": data.get("lot"),
                            "ticket": data.get("ticket"),
                            "dca_layers": []
                        }
                    elif event in ["DCA_OPEN", "DCA_ADD"]:
                        if symbol in positions:
                            positions[symbol]["dca_layers"].append({
                                "time": data.get("timestamp"),
                                "price": data.get("price"),
                                "lot": data.get("lot"),
                                "ticket": data.get("ticket"),
                                "layer": data.get("layer")
                            })
                    elif event == "CYCLE_CLOSE":
                        positions.pop(symbol, None)
            except Exception:
                pass
                
    print("\nActive positions at the time of breach:")
    if not positions:
        print("  None (or state not tracked correctly)")
    for sym, pos in positions.items():
        print(f"  Symbol: {sym} | Dir: {pos['direction']} | Lot: {pos['lot']} | Price: {pos['price']} | Ticket: {pos['ticket']}")
        for layer in pos["dca_layers"]:
            print(f"    -> DCA Layer {layer['layer']} | Lot: {layer['lot']} | Price: {layer['price']} | Ticket: {layer['ticket']}")
            
    # Also find the last few log_decision entries before the breach to see prices/indicators
    print("\nLast indicator states before breach:")
    decisions = {}
    with open(log_file, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            if idx >= breach_line:
                break
            try:
                data = json.loads(line)
                symbol = data.get("symbol")
                if symbol and "RSI_H4" in data:  # This is a log_decision entry
                    decisions[symbol] = data
            except Exception:
                pass
                
    for sym, dec in decisions.items():
        if sym in positions:
            print(f"  {sym:<8} │ Price: {dec.get('price')} │ ATR: {dec.get('ATR')} │ RSI: H4={dec.get('RSI_H4')} H1={dec.get('RSI_H1')} M15={dec.get('RSI_M15')} │ ADX: {dec.get('ADX')}")

if __name__ == "__main__":
    logs_dir = Path("d:/05_Quant/v9 Continuum/logs")
    analyze_day(logs_dir / "audit_2026-06-29.jsonl")
    analyze_day(logs_dir / "audit_2026-06-30.jsonl")
    analyze_day(logs_dir / "audit_2026-07-01.jsonl")
