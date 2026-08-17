import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import datetime
import sys
import os

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    if not mt5.initialize():
        print(f"Failed to initialize MT5: {mt5.last_error()}")
        return

    account_info = mt5.account_info()
    if account_info is None:
        print("Failed to get account info")
        mt5.shutdown()
        return

    balance = account_info.balance
    equity = account_info.equity
    currency = account_info.currency
    login = account_info.login
    server = account_info.server

    now = datetime.datetime.now()
    # Calculate Monday of current week
    start_of_week = now - datetime.timedelta(days=now.weekday(), hours=now.hour, minutes=now.minute, seconds=now.second, microseconds=now.microsecond)
    # Also fetch past 7 days to cover full rolling week
    seven_days_ago = now - datetime.timedelta(days=7)

    # 1. Fetch History Deals
    deals_week = mt5.history_deals_get(start_of_week, now + datetime.timedelta(days=1))
    deals_7d = mt5.history_deals_get(seven_days_ago, now + datetime.timedelta(days=1))
    
    # Also get all deals in August 2026
    month_start = datetime.datetime(2026, 8, 1)
    deals_month = mt5.history_deals_get(month_start, now + datetime.timedelta(days=1))

    # Helper to process deals into closed trades
    def process_deals(deals):
        if deals is None or len(deals) == 0:
            return pd.DataFrame()
        df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
        # Filter entry_out (close deals) or entry_inout
        close_deals = df[df['entry'].isin([1, 2, 3])].copy() # 1=ENTRY_OUT, 2=ENTRY_INOUT, 3=ENTRY_OUT_BY
        if close_deals.empty:
            # If no entry=1, take all non-deposit deals
            close_deals = df[df['type'].isin([0, 1])].copy()
        
        # Calculate net PnL (profit + swap + commission + fee)
        close_deals['net_pnl'] = close_deals['profit'] + close_deals.get('swap', 0) + close_deals.get('commission', 0) + close_deals.get('fee', 0)
        close_deals['time_dt'] = pd.to_datetime(close_deals['time'], unit='s')
        return close_deals

    df_week = process_deals(deals_week)
    df_7d = process_deals(deals_7d)
    df_month = process_deals(deals_month)

    # 2. Fetch Open Positions
    positions = mt5.positions_get()
    open_pnl = 0.0
    open_positions_list = []
    if positions:
        for pos in positions:
            p_dict = pos._asdict()
            open_pnl += p_dict['profit'] + p_dict.get('swap', 0)
            open_positions_list.append(p_dict)

    print("=" * 60)
    print("      CONTINUUM V9 — WEEKLY PERFORMANCE & RISK REPORT")
    print("=" * 60)
    print(f"Account: {login} ({server}) | Leverage: 1:{account_info.leverage}")
    print(f"Scan Time: {now.strftime('%Y-%m-%d %H:%M:%S')} (GMT+7)")
    print(f"Current Balance: ${balance:,.2f} | Current Equity: ${equity:,.2f}")
    print(f"Open Positions: {len(open_positions_list)} | Unrealized PnL: ${open_pnl:+,.2f}")
    print("-" * 60)

    def print_metrics(df, title):
        print(f"\n--- {title} ---")
        if df.empty:
            print("  No closed deals in this period.")
            return

        total_trades = len(df)
        wins = df[df['net_pnl'] > 0]
        losses = df[df['net_pnl'] < 0]
        bes = df[df['net_pnl'] == 0]

        win_count = len(wins)
        loss_count = len(losses)
        be_count = len(bes)
        win_rate = (win_count / total_trades) * 100 if total_trades > 0 else 0.0

        gross_profit = wins['net_pnl'].sum() if not wins.empty else 0.0
        gross_loss = abs(losses['net_pnl'].sum()) if not losses.empty else 0.0
        net_pnl = df['net_pnl'].sum()
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

        avg_win = wins['net_pnl'].mean() if not wins.empty else 0.0
        avg_loss = abs(losses['net_pnl'].mean()) if not losses.empty else 0.0
        payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0

        # Max Drawdown from closed deals equity curve
        cum_pnl = df['net_pnl'].cumsum()
        peak = np.maximum.accumulate(cum_pnl)
        drawdown = peak - cum_pnl
        max_dd = drawdown.max() if not drawdown.empty else 0.0

        print(f"  Closed Trades Count : {total_trades}")
        print(f"  Win / Loss / BE     : {win_count} Wins ({win_rate:.1f}%) | {loss_count} Losses | {be_count} BE")
        print(f"  Total Net Realized  : ${net_pnl:+,.2f}")
        print(f"  Gross Profit        : ${gross_profit:,.2f}")
        print(f"  Gross Loss          : ${gross_loss:,.2f}")
        print(f"  Profit Factor       : {profit_factor:.2f}")
        print(f"  Avg Win / Avg Loss  : ${avg_win:,.2f} / ${avg_loss:,.2f} (Payoff: {payoff_ratio:.2f}R)")
        print(f"  Max Realized DD     : ${max_dd:,.2f}")

        # Breakdown by Symbol
        print("\n  [Performance by Symbol]")
        symbols = df['symbol'].unique()
        for sym in sorted(symbols):
            sym_df = df[df['symbol'] == sym]
            sym_trades = len(sym_df)
            sym_wins = len(sym_df[sym_df['net_pnl'] > 0])
            sym_wr = (sym_wins / sym_trades) * 100 if sym_trades > 0 else 0
            sym_pnl = sym_df['net_pnl'].sum()
            print(f"    • {sym:<10}: {sym_trades:2d} trades | WR: {sym_wr:5.1f}% | Net PnL: ${sym_pnl:+7.2f}")

    # Print This Week (from Monday)
    print_metrics(df_week, f"THIS WEEK PERFORMANCE (Since Mon {start_of_week.strftime('%Y-%m-%d')})")
    
    # Print Past 7 Days
    print_metrics(df_7d, f"ROLLING 7-DAY PERFORMANCE (Since {seven_days_ago.strftime('%Y-%m-%d')})")

    # Print Open Positions Detail
    if open_positions_list:
        print("\n" + "=" * 60)
        print("                 CURRENT OPEN POSITIONS")
        print("=" * 60)
        for p in open_positions_list:
            dir_str = "BUY" if p['type'] == 0 else "SELL"
            print(f"  Ticket: {p['ticket']} | {p['symbol']} {dir_str} {p['volume']:.2f} lot | Open: {p['price_open']} | Current: {p['price_current']} | PnL: ${p['profit']:+,.2f} | Comment: {p.get('comment', '')}")

    mt5.shutdown()

if __name__ == "__main__":
    main()
