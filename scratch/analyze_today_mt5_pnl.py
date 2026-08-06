import sys
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5
import pandas as pd
import numpy as np

if not mt5.initialize():
    print("MT5 initialization failed.")
    sys.exit(1)

acc_info = mt5.account_info()
if acc_info is None:
    print("Failed to get account info.")
    mt5.shutdown()
    sys.exit(1)

print("="*85)
print(f"WORLDQUANT LIVE AUDIT ENGINE - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
print("="*85)
print(f"Account ID:          {acc_info.login}")
print(f"Server:              {acc_info.server}")
print(f"Current Balance:     ${acc_info.balance:.2f}")
print(f"Current Equity:      ${acc_info.equity:.2f}")
print(f"Margin Used:         ${acc_info.margin:.2f}")
print(f"Free Margin:         ${acc_info.free_margin if hasattr(acc_info, 'free_margin') else acc_info.margin_free:.2f}")
print(f"Floating PnL:        ${acc_info.profit:+.2f}")

# -------------------------------------------------------------
# KILL-SWITCH SAFETY BOUNDARY MONITORING
# -------------------------------------------------------------
baseline_equity_aug03 = 925.16
daily_dd_limit_usd = 32.38 # 3.5% of $925.16
total_dd_floor_usd = 814.14 # 12.0% DD floor ($925.16 - $111.02)

current_total_dd_usd = max(0.0, baseline_equity_aug03 - acc_info.equity)
current_total_dd_pct = (current_total_dd_usd / baseline_equity_aug03) * 100.0

is_total_dd_breached = acc_info.equity <= total_dd_floor_usd

print("\n" + "="*85)
print("KILL-SWITCH SAFETY BOUNDARY MONITORING")
print("="*85)
print(f"Baseline Equity (Aug 03):   ${baseline_equity_aug03:.2f}")
print(f"Max Daily DD Limit (3.5%):  -${daily_dd_limit_usd:.2f}")
print(f"Total DD Floor (12.0%):     ${total_dd_floor_usd:.2f}")
print(f"Current Equity:             ${acc_info.equity:.2f}")
print(f"Current Total DD ($ / %):   ${current_total_dd_usd:.2f} ({current_total_dd_pct:.2f}%)")
print(f"Kill-Switch Trigger Status:  {'BREACHED - TRIGGER STOP!' if is_total_dd_breached else 'OPERATIONAL (NORMAL)'}")

# -------------------------------------------------------------
# TASK 2: ASSET CLASS PNL & ALPHA CONTRIBUTION BREAKDOWN
# -------------------------------------------------------------
today_start = datetime(2026, 8, 4, 0, 0, 0, tzinfo=timezone.utc)
history_deals = mt5.history_deals_get(today_start, datetime.now(timezone.utc) + timedelta(days=1))

def categorize_symbol(sym: str) -> str:
    clean = sym.replace("m", "").upper()
    if "XAU" in clean or "GOLD" in clean:
        return "GOLD"
    elif "US500" in clean or "USTEC" in clean or "US100" in clean or "INDEX" in clean:
        return "INDICES"
    elif "BTC" in clean or "ETH" in clean:
        return "CRYPTO"
    else:
        return "FX_MAJORS"

if history_deals is not None and len(history_deals) > 0:
    df_deals = pd.DataFrame(list(history_deals), columns=history_deals[0]._asdict().keys())
    df_trades = df_deals[df_deals['entry'].isin([0, 1])].copy()
    
    # Calculate net pnl per deal
    df_trades['net_pnl'] = df_trades['profit'] + df_trades['commission'] + df_trades['swap']
    df_trades['asset_class'] = df_trades['symbol'].apply(categorize_symbol)
    
    total_net_pnl = df_trades['net_pnl'].sum()
    
    print("\n" + "="*85)
    print("TASK 2: PNL & ALPHA CONTRIBUTION BREAKDOWN BY ASSET CLASS")
    print("="*85)
    
    asset_group = df_trades.groupby('asset_class').agg(
        total_pnl=('net_pnl', 'sum'),
        deals_count=('ticket', 'count'),
        win_deals=('net_pnl', lambda x: (x > 0).sum()),
        loss_deals=('net_pnl', lambda x: (x < 0).sum())
    ).reset_index()
    
    asset_group['win_rate_pct'] = (asset_group['win_deals'] / asset_group['deals_count']) * 100.0
    asset_group['alpha_contribution_pct'] = (asset_group['total_pnl'] / abs(total_net_pnl)) * 100.0 if abs(total_net_pnl) > 0 else 0.0
    
    for idx, r in asset_group.iterrows():
        print(f"Asset Class: [{r['asset_class']:<10}] | Net PnL: ${r['total_pnl']:+7.2f} | Deals: {r['deals_count']:2d} | Win Rate: {r['win_rate_pct']:5.1f}% | Alpha Contrib: {r['alpha_contribution_pct']:+6.1f}%")
        
    print("\n" + "-"*85)
    print("SYMBOL LEVEL BREAKDOWN:")
    sym_group = df_trades.groupby('symbol').agg(
        total_pnl=('net_pnl', 'sum'),
        deals_count=('ticket', 'count'),
        win_deals=('net_pnl', lambda x: (x > 0).sum())
    ).reset_index()
    sym_group['win_rate_pct'] = (sym_group['win_deals'] / sym_group['deals_count']) * 100.0
    sym_group['alpha_contribution_pct'] = (sym_group['total_pnl'] / abs(total_net_pnl)) * 100.0 if abs(total_net_pnl) > 0 else 0.0
    
    for idx, r in sym_group.iterrows():
        print(f"  - Symbol: {r['symbol']:<10} | Net PnL: ${r['total_pnl']:+7.2f} | Deals: {r['deals_count']:2d} | Win Rate: {r['win_rate_pct']:5.1f}% | Alpha Contrib: {r['alpha_contribution_pct']:+6.1f}%")
else:
    print("\nNo history deals found for today.")

mt5.shutdown()
