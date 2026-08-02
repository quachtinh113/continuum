import json
import glob
import sys

sys.stdout.reconfigure(encoding='utf-8')

def main():
    log_files = sorted(glob.glob("logs/audit_2026-07-31.jsonl"))
    if not log_files:
        return

    signals = {}
    opens = []
    
    with open(log_files[0], "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                evt = data.get("event", "")
                sym = data.get("symbol")
                
                if "SIGNAL" in evt:
                    price = data.get("price", data.get("ask", data.get("bid")))
                    if price:
                        signals[sym] = (data.get("timestamp"), price)
                elif evt == "CYCLE_OPEN":
                    opens.append({
                        "symbol": sym,
                        "time": data.get("timestamp"),
                        "open_price": data.get("price"),
                        "last_signal": signals.get(sym)
                    })
            except Exception:
                pass

    print(f"Matched {len(opens)} CYCLE_OPEN events with recent signals:")
    for o in opens:
        sig_time, sig_price = o["last_signal"] if o["last_signal"] else ("N/A", None)
        sym = o.get("symbol", "N/A")
        open_p = o.get("open_price")
        open_p_str = f"{open_p:.5f}" if isinstance(open_p, (int, float)) else "N/A"
        time_str = o.get("time", "")[:19]
        
        pip_size = 0.01 if any(k in sym for k in ["JPY", "XAU", "US30", "US500", "US100"]) else 0.0001
        
        if sig_price and isinstance(open_p, (int, float)):
            slip_pips = abs(open_p - sig_price) / pip_size
            print(f"  - {sym:8s} | Signal: {sig_price:.5f} ({sig_time[:19]}) -> Fill: {open_p_str} ({time_str}) | Slippage: {slip_pips:.3f} pips")
        else:
            print(f"  - {sym:8s} | Fill: {open_p_str} ({time_str}) | Signal: N/A")

if __name__ == "__main__":
    main()
