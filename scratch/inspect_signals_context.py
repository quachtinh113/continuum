import json
from pathlib import Path

def print_indicator_context(log_path, lines_to_inspect):
    print(f"\n==========================================")
    print(f"INDICATOR CONTEXT AUDIT FOR: {log_path.name}")
    print(f"==========================================")
    
    if not log_path.exists():
        print("File does not exist.")
        return
        
    with open(log_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if line_num in lines_to_inspect:
                try:
                    data = json.loads(line)
                    print(f"\n--- Line {line_num} [{data.get('timestamp')}] ---")
                    print(f"Symbol: {data.get('symbol')}")
                    print(f"Session: {data.get('session')}")
                    print(f"Signal: {data.get('signal')}")
                    print(f"Risk Decision: {data.get('risk_decision')}")
                    print(f"Execution Action: {data.get('execution_action')}")
                    print(f"Reason: {data.get('reason')}")
                    
                    # Print indicators if present
                    indicators = {
                        "RSI_H4": data.get("RSI_H4"),
                        "RSI_H1": data.get("RSI_H1"),
                        "RSI_M15": data.get("RSI_M15"),
                        "ADX": data.get("ADX"),
                        "ATR": data.get("ATR")
                    }
                    print(f"Technical Indicators: {indicators}")
                    
                    # Print features if present
                    # (Note: keys in the json itself might be flat)
                    # We can print flat keys that are in EXTENDED_FEATURES
                    feat_keys = ['RSI_Delta', 'Volatility_Index', 'Session_Code', 'RSI_H1_Div', 'Trend_Vol_Ratio', 'hour']
                    features = {k: data.get(k) for k in feat_keys if k in data}
                    if features:
                        print(f"Model Features: {features}")
                except Exception as e:
                    print(f"Line {line_num} error: {e}")

if __name__ == "__main__":
    project_root = Path("d:/05_Quant/v9 Continuum")
    # Inspect lines 12068 and 12070 (decision logs for GBPUSD and XAUUSD SELL entry)
    print_indicator_context(project_root / "logs" / "audit_2026-06-24.jsonl", [12068, 12070])
