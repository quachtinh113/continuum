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
print(f"WORLDQUANT WEEKLY LIVE AUDIT ENGINE - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
print("="*85)
print(f"Account ID:          {acc_info.login}")
print(f"Server:              {acc_info.server}")
print(f"Current Balance:     ${acc_info.balance:.2f}")
print(f"Current Equity:      ${acc_info.equity:.2f}")
print(f"Margin Used:         ${acc_info.margin:.2f}")
print(f"Free Margin:         ${acc_info.free_margin if hasattr(acc_info, 'free_margin') else acc_info.margin_free:.2f}")
print(f"Floating PnL:        ${acc_info.profit:+.2f}")

# -------------------------------------------------------------
# WEEKLY PERFORMANCE ANALYSIS (AUG 03 - AUG 06, 2026)
# -------------------------------------------------------------
baseline_equity_aug03 = 925.16
weekly_net_growth_usd = acc_info.equity - baseline_equity_aug03
weekly_net_growth_pct = (weekly_net_growth_usd / baseline_equity_aug03) * 100.0

week_start = datetime(2026, 8, 3, 0, 0, 0, tzinfo=timezone.utc)
history_deals = mt5.history_deals_get(week_start, datetime.now(timezone.utc) + timedelta(days=1))

def categorize_symbol(sym: str) -> str:
    clean = sym.replace("m", "").upper()
    if "XAU" in clean or "GOLD" in clean:
        return "GOLD"
    elif "US500" in clean or "USTEC" in clean or "US100" in clean or "US30" in clean:
        return "INDICES"
    elif "BTC" in clean or "ETH" in clean:
        return "CRYPTO"
    else:
        return "FX_MAJORS"

if history_deals is not None and len(history_deals) > 0:
    df_deals = pd.DataFrame(list(history_deals), columns=history_deals[0]._asdict().keys())
    df_trades = df_deals[df_deals['entry'].isin([0, 1])].copy()
    df_trades['net_pnl'] = df_trades['profit'] + df_trades['commission'] + df_trades['swap']
    df_trades['asset_class'] = df_trades['symbol'].apply(categorize_symbol)
    
    total_net_pnl = df_trades['net_pnl'].sum()
    total_deals = len(df_trades)
    win_deals = df_trades[df_trades['net_pnl'] > 0]
    loss_deals = df_trades[df_trades['net_pnl'] < 0]
    win_rate = (len(win_deals) / total_deals * 100.0) if total_deals > 0 else 0.0
    
    print("\n" + "="*85)
    print("WEEKLY PERFORMANCE METRICS (AUG 03 - AUG 06, 2026)")
    print("="*85)
    print(f"Starting Baseline Equity (Aug 03): ${baseline_equity_aug03:.2f}")
    print(f"Current Account Equity (Aug 06):  ${acc_info.equity:.2f}")
    print(f"Weekly Net Growth ($ / %):        +${weekly_net_growth_usd:,.2f} (+{weekly_net_growth_pct:.2f}%)")
    print(f"Total Trade Deals Executed:       {total_deals} deals")
    print(f"Overall Win Rate (%):             {win_rate:.1f}% ({len(win_deals)} Wins / {len(loss_deals)} Losses)")
    print(f"Gross Profit:                     ${win_deals['net_pnl'].sum():+.2f}")
    print(f"Gross Loss:                       ${loss_deals['net_pnl'].sum():+.2f}")
    
    print("\n" + "="*85)
    print("ASSET CLASS BREAKDOWN (WEEKLY)")
    print("="*85)
    
    asset_group = df_trades.groupby('asset_class').agg(
        total_pnl=('net_pnl', 'sum'),
        deals_count=('ticket', 'count'),
        win_deals=('net_pnl', lambda x: (x > 0).sum())
    ).reset_index()
    
    asset_group['win_rate_pct'] = (asset_group['win_deals'] / asset_group['deals_count']) * 100.0
    asset_group['alpha_contrib_pct'] = (asset_group['total_pnl'] / abs(total_net_pnl)) * 100.0 if abs(total_net_pnl) > 0 else 0.0
    
    for idx, r in asset_group.iterrows():
        print(f"Asset Class: [{r['asset_class']:<10}] | Net PnL: ${r['total_pnl']:+7.2f} | Deals: {r['deals_count']:2d} | Win Rate: {r['win_rate_pct']:5.1f}% | Alpha Contrib: {r['alpha_contrib_pct']:+6.1f}%")

    print("\n" + "-"*85)
    print("SYMBOL LEVEL BREAKDOWN (WEEKLY):")
    sym_group = df_trades.groupby('symbol').agg(
        total_pnl=('net_pnl', 'sum'),
        deals_count=('ticket', 'count'),
        win_deals=('net_pnl', lambda x: (x > 0).sum())
    ).reset_index()
    sym_group['win_rate_pct'] = (sym_group['win_deals'] / sym_group['deals_count']) * 100.0
    sym_group['alpha_contrib_pct'] = (sym_group['total_pnl'] / abs(total_net_pnl)) * 100.0 if abs(total_net_pnl) > 0 else 0.0
    
    for idx, r in sym_group.iterrows():
        print(f"  - Symbol: {r['symbol']:<10} | Net PnL: ${r['total_pnl']:+7.2f} | Deals: {r['deals_count']:2d} | Win Rate: {r['win_rate_pct']:5.1f}% | Alpha Contrib: {r['alpha_contrib_pct']:+6.1f}%")

# Active positions check
positions = mt5.positions_get()
print("\n" + "="*85)
print("ACTIVE POSITIONS MONITORING")
print("="*85)
if positions is None or len(positions) == 0:
    print("No active open positions. Portfolio 100% in cash.")
else:
    for p in positions:
        pos_time = datetime.fromtimestamp(p.time, tz=timezone.utc).strftime('%m-%d %H:%M:%S')
        pos_type = "BUY" if p.type == 0 else "SELL"
        print(f"  [{pos_time}] Ticket: {p.ticket} | {p.symbol} | {pos_type} {p.volume:.2f} lot | Entry: {p.price_open:.5f} | Current: {p.price_current:.5f} | Floating: ${p.profit:+.2f}")

mt5.shutdown()
