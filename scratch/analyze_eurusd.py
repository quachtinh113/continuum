import json
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(r"d:\05_Quant\NOWTRAEDING")
LOGS_DIR = PROJECT_ROOT / "logs"

def analyze_eurusd():
    log_path = LOGS_DIR / "audit_2026-06-15.jsonl"
    if not log_path.exists():
        print("Audit log for 15th June not found.")
        return
        
    eurusd_closes = []
    eurusd_opens = []
    
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line.strip())
                event = data.get("event")
                symbol = data.get("symbol")
                
                if symbol == "EURUSD":
                    if event == "CYCLE_CLOSE":
                        eurusd_closes.append(data)
                    elif event == "CYCLE_OPEN":
                        eurusd_opens.append(data)
            except Exception:
                pass
                
    print(f"EURUSD on 15th June: Opens={len(eurusd_opens)}, Closes={len(eurusd_closes)}")
    
    if eurusd_closes:
        df = pd.DataFrame(eurusd_closes)
        df["profit_usd"] = df["profit_usd"].astype(float)
        df["holding_hours"] = df["holding_hours"].astype(float)
        
        print("\n=== EURUSD CLOSE REASONS ===")
        print(df["reason"].value_counts().to_string())
        
        print("\n=== EURUSD PNL STATISTICS ===")
        print(f"Total PnL: ${df['profit_usd'].sum():.2f}")
        print(f"Average PnL: ${df['profit_usd'].mean():.2f}")
        print(f"Max Win: ${df['profit_usd'].max():.2f}")
        print(f"Max Loss: ${df['profit_usd'].min():.2f}")
        
        print("\n=== EURUSD HOLDING HOURS BY REASON ===")
        print(df.groupby("reason")["holding_hours"].mean().to_string())
        
        # Look at lot sizes
        if "total_lots" in df.columns:
            df["total_lots"] = df["total_lots"].astype(float)
            print("\n=== EURUSD LOT SIZES ===")
            print(df["total_lots"].value_counts().to_string())
            
        # Let's print first 5 closes to see details
        print("\n=== EXAMPLE OF FIRST 5 CLOSES ===")
        cols_to_show = ["ticket", "reason", "profit_usd", "holding_hours", "total_lots", "dca_layers"]
        cols_exist = [c for c in cols_to_show if c in df.columns]
        print(df[cols_exist].head(5).to_string())
        
    else:
        print("No EURUSD closes found.")

if __name__ == "__main__":
    analyze_eurusd()
