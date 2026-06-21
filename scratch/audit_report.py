import json
import pandas as pd
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(r"d:\05_Quant\NOWTRAEDING")
LOGS_DIR = PROJECT_ROOT / "logs"

def analyze_audit_files():
    audit_files = sorted(list(LOGS_DIR.glob("audit_2026-06-*.jsonl")))
    
    all_closes = []
    all_opens = []
    ml_vetoes = []
    
    for file_path in audit_files:
        date_str = file_path.stem.split("_")[1]
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line.strip())
                    event = data.get("event")
                    execution_action = data.get("execution_action")
                    
                    if event == "CYCLE_CLOSE":
                        # Add date context if not present
                        if "date" not in data:
                            data["date"] = date_str
                        all_closes.append(data)
                    elif event == "CYCLE_OPEN":
                        if "date" not in data:
                            data["date"] = date_str
                        all_opens.append(data)
                    
                    if execution_action == "ML_BLOCKED":
                        ml_vetoes.append(data)
                except Exception as e:
                    pass
                    
    print(f"Loaded {len(all_opens)} opens, {len(all_closes)} closes, {len(ml_vetoes)} ML vetoes.\n")
    
    # ── Analyze Closes ──
    if all_closes:
        df_closes = pd.DataFrame(all_closes)
        df_closes["profit_usd"] = df_closes["profit_usd"].astype(float)
        df_closes["total_lots"] = df_closes["total_lots"].astype(float)
        df_closes["holding_hours"] = df_closes["holding_hours"].astype(float)
        df_closes["dca_layers"] = df_closes["dca_layers"].astype(int)
        
        print("=== COMPLETED TRADES STATISTICS ===")
        print(f"Total Closed Trades: {len(df_closes)}")
        total_pnl = df_closes["profit_usd"].sum()
        print(f"Total PnL (USD): ${total_pnl:.2f}")
        
        wins = df_closes[df_closes["profit_usd"] > 0]
        losses = df_closes[df_closes["profit_usd"] <= 0]
        win_rate = len(wins) / len(df_closes) * 100 if len(df_closes) > 0 else 0
        
        print(f"Win Rate: {win_rate:.2f}% ({len(wins)} Wins / {len(losses)} Losses)")
        print(f"Average Profit per Win: ${wins['profit_usd'].mean():.2f}" if len(wins) > 0 else "N/A")
        print(f"Average Loss per Loss: ${losses['profit_usd'].mean():.2f}" if len(losses) > 0 else "N/A")
        print(f"Max Win: ${df_closes['profit_usd'].max():.2f}")
        print(f"Max Loss: ${df_closes['profit_usd'].min():.2f}")
        print(f"Average Holding Time (hours): {df_closes['holding_hours'].mean():.2f}")
        print(f"Average DCA Layers: {df_closes['dca_layers'].mean():.2f}")
        
        # PnL by Date
        print("\n=== PNL BY DATE ===")
        pnl_by_date = df_closes.groupby("date")["profit_usd"].agg(["sum", "count", "mean"])
        print(pnl_by_date.to_string())
        
        # PnL by Symbol
        print("\n=== PNL BY SYMBOL ===")
        pnl_by_symbol = df_closes.groupby("symbol")["profit_usd"].agg(["sum", "count", "mean"])
        print(pnl_by_symbol.to_string())
        
        # Win rate by DCA layers
        print("\n=== PERFORMANCE BY DCA LAYERS ===")
        dca_perf = df_closes.groupby("dca_layers")["profit_usd"].agg(["sum", "count", lambda x: (x > 0).mean() * 100])
        dca_perf.columns = ["Sum PnL", "Count", "Win Rate %"]
        print(dca_perf.to_string())
        
    else:
        print("No closed trades found.")

    # ── Analyze ML Vetoes ──
    print("\n=== ML GATEKEEPER VETO STATISTICS ===")
    if ml_vetoes:
        df_veto = pd.DataFrame(ml_vetoes)
        print(f"Total trades blocked by ML Gatekeeper: {len(df_veto)}")
        if "symbol" in df_veto.columns:
            print("\nVetoes by Symbol:")
            print(df_veto["symbol"].value_counts().to_string())
    else:
        print("No ML vetoes recorded in the audit logs.")

if __name__ == "__main__":
    analyze_audit_files()
