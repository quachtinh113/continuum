import json
import pandas as pd
from pathlib import Path
from datetime import datetime

import sys

# Path to the logs directory in the workspace
LOGS_DIR = Path(r"d:\05_Quant\v9 Continuum\logs")

def analyze_pnl():
    sys.stdout.reconfigure(encoding='utf-8')
    # Glob for July 2026 audit logs
    # Today is July 18, 2026, so the past week would be July 12 to July 18, 2026.
    audit_files = sorted(list(LOGS_DIR.glob("audit_2026-07-*.jsonl")))
    
    all_closes = []
    all_opens = []
    errors = []
    
    for file_path in audit_files:
        date_str = file_path.stem.split("_")[1]
        # We only want dates from 2026-07-12 to 2026-07-18
        try:
            day = int(date_str.split("-")[2])
            if not (12 <= day <= 18):
                continue
        except Exception:
            continue
            
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line.strip())
                    event = data.get("event")
                    severity = data.get("severity")
                    
                    if severity in ["ERROR", "WARNING"] or event == "ERROR":
                        data["date"] = date_str
                        errors.append(data)
                        
                    if event == "CYCLE_CLOSE":
                        if "date" not in data:
                            data["date"] = date_str
                        all_closes.append(data)
                    elif event == "CYCLE_OPEN":
                        if "date" not in data:
                            data["date"] = date_str
                        all_opens.append(data)
                except Exception as e:
                    pass
                    
    print(f"Loaded {len(all_opens)} opens, {len(all_closes)} closes, {len(errors)} errors/warnings for the week of July 12 to July 18, 2026.\n")
    
    if all_closes:
        df_closes = pd.DataFrame(all_closes)
        
        # Ensure correct column types
        for col in ["profit_usd", "total_lots", "holding_hours"]:
            if col in df_closes.columns:
                df_closes[col] = pd.to_numeric(df_closes[col], errors='coerce').fillna(0.0)
            else:
                df_closes[col] = 0.0
                
        if "dca_layers" in df_closes.columns:
            df_closes["dca_layers"] = pd.to_numeric(df_closes["dca_layers"], errors='coerce').fillna(0).astype(int)
        else:
            df_closes["dca_layers"] = 0
            
        total_pnl = df_closes["profit_usd"].sum()
        
        # Total volume traded
        total_lots = df_closes["total_lots"].sum() if "total_lots" in df_closes.columns else 0.0
        
        print("==================================================================")
        print("📊 COMPLETED TRADES STATISTICS (July 12 - July 18, 2026)")
        print("==================================================================")
        print(f"Total Closed Trades       │ {len(df_closes)}")
        print(f"Total Net PnL (USD)       │ ${total_pnl:.2f}")
        print(f"Total Volume traded (Lots)│ {total_lots:.2f}")
        
        wins = df_closes[df_closes["profit_usd"] > 0]
        losses = df_closes[df_closes["profit_usd"] <= 0]
        win_rate = len(wins) / len(df_closes) * 100 if len(df_closes) > 0 else 0
        
        print(f"Win Rate                  │ {win_rate:.2f}% ({len(wins)} Wins / {len(losses)} Losses)")
        print(f"Gross Profit (Wins)       │ ${wins['profit_usd'].sum():.2f}")
        print(f"Gross Loss (Losses)       │ ${losses['profit_usd'].sum():.2f}")
        
        gross_loss = losses['profit_usd'].sum()
        if gross_loss != 0:
            print(f"Profit Factor             │ {abs(wins['profit_usd'].sum() / gross_loss):.2f}")
        else:
            print("Profit Factor             │ N/A")
            
        print(f"Average Profit per Win    │ ${wins['profit_usd'].mean():.2f}" if len(wins) > 0 else "N/A")
        print(f"Average Loss per Loss     │ ${losses['profit_usd'].mean():.2f}" if len(losses) > 0 else "N/A")
        print(f"Max Win                   │ ${df_closes['profit_usd'].max():.2f}" if len(df_closes) > 0 else "N/A")
        print(f"Max Loss                  │ ${df_closes['profit_usd'].min():.2f}" if len(df_closes) > 0 else "N/A")
        
        if "holding_hours" in df_closes.columns:
            print(f"Avg Holding Time (hours)  │ {df_closes['holding_hours'].mean():.2f}")
        if "dca_layers" in df_closes.columns:
            print(f"Avg DCA Layers per Cycle  │ {df_closes['dca_layers'].mean():.2f}")
        print("==================================================================\n")
        
        # PnL by Date
        print("📈 PNL BY DATE:")
        print("------------------------------------------------------------------")
        pnl_by_date = df_closes.groupby("date")["profit_usd"].agg(["sum", "count", "mean"])
        pnl_by_date.columns = ["Sum PnL", "Count", "Mean PnL"]
        print(pnl_by_date.to_string())
        print("------------------------------------------------------------------\n")
        
        # PnL by Symbol
        print("💱 PNL BY SYMBOL:")
        print("------------------------------------------------------------------")
        pnl_by_symbol = df_closes.groupby("symbol")["profit_usd"].agg(["sum", "count", "mean"])
        pnl_by_symbol.columns = ["Sum PnL", "Count", "Mean PnL"]
        print(pnl_by_symbol.to_string())
        print("------------------------------------------------------------------\n")
        
        # Performance by DCA layers
        if "dca_layers" in df_closes.columns:
            print("🧱 PERFORMANCE BY DCA LAYERS:")
            print("------------------------------------------------------------------")
            dca_perf = df_closes.groupby("dca_layers")["profit_usd"].agg(["sum", "count", lambda x: (x > 0).mean() * 100])
            dca_perf.columns = ["Sum PnL", "Count", "Win Rate %"]
            print(dca_perf.to_string())
            print("------------------------------------------------------------------\n")
        
        # List of individual trades
        print("📝 INDIVIDUAL TRADES:")
        print("------------------------------------------------------------------")
        cols_to_print = ["date", "symbol", "direction", "total_lots", "dca_layers", "profit_usd", "holding_hours"]
        # check which columns exist
        cols_to_print = [c for c in cols_to_print if c in df_closes.columns]
        print(df_closes[cols_to_print].to_string(index=False))
        print("------------------------------------------------------------------\n")
    else:
        print("No closed trades found in this date range.")

    if errors:
        print("❌ ERRORS / WARNINGS DURING THE WEEK:")
        print("------------------------------------------------------------------")
        for err in errors[:20]: # show first 20
            timestamp = err.get("timestamp", "")
            if len(timestamp) > 19:
                timestamp = timestamp[11:19]
            print(f"[{err.get('date')}] [{timestamp}] {err.get('severity') or err.get('event')}: {err.get('message') or err.get('reason')}")
        if len(errors) > 20:
            print(f"... and {len(errors) - 20} more errors/warnings.")
        print("------------------------------------------------------------------\n")

if __name__ == "__main__":
    analyze_pnl()
