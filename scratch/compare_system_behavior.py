import json
import pandas as pd
from pathlib import Path
from datetime import datetime
import sys

LOGS_DIR = Path(r"d:\05_Quant\v9 Continuum\logs")

def analyze_week_logs(start_day, end_day):
    log_files = sorted(list(LOGS_DIR.glob("audit_2026-07-*.jsonl")))
    
    total_lines = 0
    errors_count = 0
    warnings_count = 0
    ipc_timeouts = 0
    reconnect_failures = 0
    drawdown_locks = 0
    governor_vetoes = 0
    bot_startups = 0
    
    veto_reasons = {}
    
    for log_file in log_files:
        date_str = log_file.stem.split("_")[1]
        try:
            day = int(date_str.split("-")[2])
            if not (start_day <= day <= end_day):
                continue
        except Exception:
            continue
            
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                total_lines += 1
                try:
                    data = json.loads(line.strip())
                    msg = data.get("message") or data.get("reason") or ""
                    severity = data.get("severity", "")
                    event = data.get("event", "")
                    risk_decision = str(data.get("risk_decision") or "")
                    execution_action = str(data.get("execution_action") or "")
                    
                    # Detect Bot Startups
                    if event == "STARTUP" or "initializing" in msg.lower() or "starting bot" in msg.lower():
                        bot_startups += 1
                        
                    if severity == "ERROR":
                        errors_count += 1
                    elif severity == "WARNING":
                        warnings_count += 1
                        
                    if "IPC timeout" in msg or "initialize failed" in msg.lower():
                        ipc_timeouts += 1
                        
                    if "reconnect failed" in msg.lower():
                        reconnect_failures += 1
                        
                    if "drawdown limit breached" in msg.lower() or "LOCKED by global drawdown limit" in msg:
                        if "Drawdown Limit Breached" in msg or "LOCKED" in msg:
                            # Let's count actual lock event or message containing "Emergency closing"
                            if "Drawdown Limit Breached" in msg:
                                drawdown_locks += 1
                            
                    # Detect Governor vetoes/blocks
                    if "VETOED" in risk_decision or "BLOCKED" in execution_action or "governor blocked" in msg.lower():
                        governor_vetoes += 1
                        reason = data.get("reason") or msg
                        # Clean prefix if any
                        if "Governor blocked: " in reason:
                            reason = reason.replace("Governor blocked: ", "")
                        veto_reasons[reason] = veto_reasons.get(reason, 0) + 1
                except Exception as e:
                    pass
                    
    return {
        'total_lines': total_lines,
        'errors': errors_count,
        'warnings': warnings_count,
        'ipc_timeouts': ipc_timeouts,
        'reconnect_failures': reconnect_failures,
        'drawdown_locks': drawdown_locks,
        'governor_vetoes': governor_vetoes,
        'bot_startups': bot_startups,
        'veto_reasons': veto_reasons
    }

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("Analyzing last week (July 13 - July 19)...")
    last_week = analyze_week_logs(13, 19)
    
    print("Analyzing this week (July 20 - July 25)...")
    this_week = analyze_week_logs(20, 25)
    
    print("\n==================================================================")
    print("🖥️ COMPARISON OF SYSTEM BEHAVIOR & DIAGNOSTICS")
    print("==================================================================")
    
    metrics = [
        ("Total Log Lines Analyzed", 'total_lines'),
        ("Total ERROR Events", 'errors'),
        ("Total WARNING Events", 'warnings'),
        ("MT5 IPC Timeout Warnings", 'ipc_timeouts'),
        ("MT5 Reconnect Failures", 'reconnect_failures'),
        ("Emergency Drawdown Locks", 'drawdown_locks'),
        ("Governor Trade Vetoes", 'governor_vetoes'),
        ("Bot Startups/Restarts", 'bot_startups')
    ]
    
    print(f"{'Metric':<30} │ {'Last Week (13-19)':<18} │ {'This Week (20-25)':<18}")
    print("-" * 72)
    for label, key in metrics:
        print(f"{label:<30} │ {last_week[key]:<18} │ {this_week[key]:<18}")
        
    print("\n==================================================================")
    print("🎯 GOVERNOR VETOES DETAILS")
    print("==================================================================")
    print("\nLast Week Veto Reasons:")
    for reason, count in sorted(last_week['veto_reasons'].items(), key=lambda x: x[1], reverse=True):
        print(f"  - {reason}: {count} times")
        
    print("\nThis Week Veto Reasons:")
    for reason, count in sorted(this_week['veto_reasons'].items(), key=lambda x: x[1], reverse=True):
        print(f"  - {reason}: {count} times")

if __name__ == "__main__":
    main()
