import MetaTrader5 as mt5
import pandas as pd
import sys
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

LOGS_DIR = Path(r"d:\05_Quant\v9 Continuum\logs")

def get_week_stats(from_date, to_date):
    deals = mt5.history_deals_get(from_date, to_date)
    if deals is None or len(deals) == 0:
        return None
        
    df_deals = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    df_deals['time'] = pd.to_datetime(df_deals['time'], unit='s')
    
    # Map entry and type to string
    df_deals['entry_str'] = df_deals['entry'].map({0: 'IN', 1: 'OUT', 2: 'INOUT'}).fillna(df_deals['entry'])
    df_deals['type_str'] = df_deals['type'].map({0: 'BUY', 1: 'SELL'}).fillna(df_deals['type'])
    
    # Out deals represent closures
    df_out = df_deals[df_deals['entry'] == 1].copy()
    
    total_deals = len(df_deals)
    total_in = len(df_deals[df_deals['entry'] == 0])
    total_out = len(df_out)
    
    # Sum up totals
    gross_profit = df_deals['profit'].sum()
    total_commission = df_deals['commission'].sum() if 'commission' in df_deals.columns else 0.0
    total_swap = df_deals['swap'].sum() if 'swap' in df_deals.columns else 0.0
    net_pnl = gross_profit + total_commission + total_swap
    
    stats = {
        'total_deals': total_deals,
        'total_in': total_in,
        'total_out': total_out,
        'gross_profit': gross_profit,
        'commission': total_commission,
        'swap': total_swap,
        'net_pnl': net_pnl,
        'win_rate': 0.0,
        'wins_count': 0,
        'losses_count': 0,
        'profit_factor': 0.0,
        'avg_win': 0.0,
        'avg_loss': 0.0,
        'max_win': 0.0,
        'max_loss': 0.0,
        'df_out': df_out,
        'df_deals': df_deals
    }
    
    if total_out > 0:
        wins = df_out[df_out['profit'] > 0]
        losses = df_out[df_out['profit'] <= 0]
        stats['win_rate'] = len(wins) / total_out * 100
        stats['wins_count'] = len(wins)
        stats['losses_count'] = len(losses)
        stats['wins_sum'] = wins['profit'].sum()
        stats['losses_sum'] = losses['profit'].sum()
        
        loss_sum = losses['profit'].sum()
        if loss_sum != 0:
            stats['profit_factor'] = abs(wins['profit'].sum() / loss_sum)
        else:
            stats['profit_factor'] = float('inf')
            
        stats['avg_win'] = wins['profit'].mean() if len(wins) > 0 else 0.0
        stats['avg_loss'] = losses['profit'].mean() if len(losses) > 0 else 0.0
        stats['max_win'] = df_out['profit'].max()
        stats['max_loss'] = df_out['profit'].min()
        
    return stats

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("Connecting to MetaTrader 5...")
    if not mt5.initialize():
        print(f"Failed to initialize MT5: {mt5.last_error()}")
        sys.exit(1)
        
    account_info = mt5.account_info()
    if account_info is None:
        print("Failed to get account info.")
        mt5.shutdown()
        sys.exit(1)
        
    print(f"Connected to Account: {account_info.login}")
    print(f"Balance: ${account_info.balance:.2f} | Equity: ${account_info.equity:.2f}\n")

    # Dates
    # This week: Monday, July 20, 2026 00:00:00 to now
    this_week_start = datetime(2026, 7, 20, 0, 0, 0, tzinfo=timezone.utc)
    utc_now = datetime.now(timezone.utc)
    
    # Last week: Monday, July 13, 2026 00:00:00 to Sunday, July 19, 2026 23:59:59
    last_week_start = datetime(2026, 7, 13, 0, 0, 0, tzinfo=timezone.utc)
    last_week_end = datetime(2026, 7, 19, 23, 59, 59, tzinfo=timezone.utc)
    
    print("Calculating statistics for Last Week...")
    last_week_stats = get_week_stats(last_week_start, last_week_end)
    
    print("Calculating statistics for This Week...")
    this_week_stats = get_week_stats(this_week_start, utc_now)
    
    print("\n==================================================================")
    print("📈 WEEKLY PERFORMANCE COMPARISON")
    print("==================================================================")
    
    def print_week(name, stats):
        print(f"\n--- {name} ---")
        if stats is None:
            print("No trading activity found.")
            return
        print(f"Net Account PnL           │ ${stats['net_pnl']:+.2f}")
        print(f"Total Closed Positions (OUT)│ {stats['total_out']}")
        print(f"Win Rate (Closed Trades)  │ {stats['win_rate']:.2f}% ({stats['wins_count']} Wins / {stats['losses_count']} Losses)")
        print(f"Profit Factor             │ {stats['profit_factor']:.2f}" if stats['profit_factor'] != float('inf') else "Profit Factor             │ N/A")
        print(f"Gross Profit/Loss (Deals) │ ${stats['gross_profit']:+.2f}")
        print(f"Total Commissions         │ ${stats['commission']:+.2f}")
        print(f"Total Swap Fees           │ ${stats['swap']:+.2f}")
        print(f"Average Profit per Win    │ ${stats['avg_win']:+.2f}" if stats['wins_count'] > 0 else "Average Profit per Win    │ N/A")
        print(f"Average Loss per Loss     │ ${stats['avg_loss']:+.2f}" if stats['losses_count'] > 0 else "Average Loss per Loss     │ N/A")
        print(f"Max Win / Max Loss        │ ${stats['max_win']:+.2f} / ${stats['max_loss']:+.2f}")
        
        # PnL by Symbol
        df_deals = stats['df_deals']
        symbol_groups = df_deals.groupby('symbol').agg(
            gross_pnl=('profit', 'sum'),
            commissions=('commission', 'sum'),
            swaps=('swap', 'sum'),
            trades_closed=('entry', lambda x: (x == 1).sum())
        )
        symbol_groups['net_pnl'] = symbol_groups['gross_pnl'] + symbol_groups['commissions'] + symbol_groups['swaps']
        print("\nPnL by Symbol:")
        print(symbol_groups[['trades_closed', 'gross_pnl', 'net_pnl']].to_string())
        
    print_week("LAST WEEK (July 13 - July 19)", last_week_stats)
    print_week("THIS WEEK (July 20 - July 25)", this_week_stats)
    
    print("\n==================================================================")
    print("🛡️ SYSTEM STATUS & DIAGNOSTICS")
    print("==================================================================")
    
    # Check active positions
    positions = mt5.positions_get()
    if positions is not None and len(positions) > 0:
        print(f"Active Positions: {len(positions)} open")
        df_pos = pd.DataFrame(list(positions), columns=positions[0]._asdict().keys())
        df_pos['time'] = pd.to_datetime(df_pos['time'], unit='s')
        df_pos['type'] = df_pos['type'].map({0: 'BUY', 1: 'SELL'}).fillna(df_pos['type'])
        cols = ['time', 'symbol', 'type', 'volume', 'price_open', 'price_current', 'profit', 'comment']
        existing_cols = [c for c in cols if c in df_pos.columns]
        print(df_pos[existing_cols].to_string(index=False))
    else:
        print("No active positions currently open.")
        
    # Scan audit logs of this week for locks/errors
    print("\nScanning audit logs from July 20 to July 25, 2026 for errors/warnings...")
    log_files = sorted(list(LOGS_DIR.glob("audit_2026-07-*.jsonl")))
    
    locks = []
    errors = []
    
    for log_file in log_files:
        date_str = log_file.stem.split("_")[1]
        try:
            day = int(date_str.split("-")[2])
            if not (20 <= day <= 25):
                continue
        except Exception:
            continue
            
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line.strip())
                    msg = data.get("message", "")
                    severity = data.get("severity", "")
                    
                    if "LOCKED" in msg or "lock" in msg.lower() or "drawdown limit breached" in msg.lower():
                        data['date'] = date_str
                        locks.append(data)
                        
                    if severity in ["ERROR", "WARNING"]:
                        data['date'] = date_str
                        errors.append(data)
                except Exception:
                    pass
                    
    print(f"Total system locks/drawdown alerts this week: {len(locks)}")
    print(f"Total ERRORS/WARNINGS logged this week: {len(errors)}")
    
    if len(locks) > 0:
        print("\nLast 5 System Lock/Drawdown Alerts:")
        for l in locks[-5:]:
            print(f"  [{l.get('date')} {l.get('timestamp', '').split(' ')[-1]}] {l.get('message')}")
            
    if len(errors) > 0:
        print("\nLast 5 Error/Warning events:")
        for e in errors[-5:]:
            print(f"  [{e.get('date')} {e.get('timestamp', '').split(' ')[-1]}] {e.get('severity')} │ {e.get('message')}")
            
    # Check if watchdog/bot pid is running
    print("\nChecking if bot process is running...")
    bot_pid_file = LOGS_DIR / "bot.pid"
    if bot_pid_file.exists():
        try:
            with open(bot_pid_file, "r") as f:
                pid = int(f.read().strip())
            
            # Simple check without psutil
            import subprocess
            output = subprocess.check_output(f'tasklist /FI "PID eq {pid}"', shell=True).decode('utf-8', errors='ignore')
            if str(pid) in output:
                print(f"Bot process (PID {pid}) is running.")
            else:
                print(f"Bot PID {pid} is NOT running (dead process).")
        except Exception as e:
            print(f"Could not check PID file: {e}")
    else:
        print("bot.pid file not found.")

    mt5.shutdown()

if __name__ == "__main__":
    main()
