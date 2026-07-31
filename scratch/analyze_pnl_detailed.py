import MetaTrader5 as mt5
import pandas as pd
import sys
from datetime import datetime, timedelta, timezone

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    if not mt5.initialize():
        print(f"Failed to initialize MT5: {mt5.last_error()}")
        return

    account_info = mt5.account_info()
    if account_info is None:
        print("Failed to get account info.")
        mt5.shutdown()
        return

    print("==================================================================")
    print("📊 HỆ THỐNG QUẢN LÝ TÀI KHỎAN MT5 & PNL TRADING")
    print("==================================================================")
    print(f"Account ID:      {account_info.login}")
    print(f"Server:          {account_info.server}")
    print(f"Currency:        {account_info.currency}")
    print(f"Balance:         ${account_info.balance:,.2f}")
    print(f"Equity:          ${account_info.equity:,.2f}")
    print(f"Free Margin:     ${account_info.margin_free:,.2f}")

    # Check open positions
    positions = mt5.positions_get()
    if positions:
        print(f"\n🟢 LỆNH ĐANG MỞ (OPEN POSITIONS): {len(positions)} vị thế")
        df_pos = pd.DataFrame(list(positions), columns=positions[0]._asdict().keys())
        df_pos['type_str'] = df_pos['type'].map({0: 'BUY', 1: 'SELL'})
        df_pos['time'] = pd.to_datetime(df_pos['time'], unit='s')
        total_open_pnl = df_pos['profit'].sum()
        for idx, row in df_pos.iterrows():
            print(f"  • [{row['time'].strftime('%m-%d %H:%M')}] {row['symbol']} {row['type_str']} {row['volume']} lot @ {row['price_open']} | Floating PnL: ${row['profit']:+.2f}")
        print(f"  => Tổng Floating PnL: ${total_open_pnl:+.2f}")
    else:
        print("\n⚪ LỆNH ĐANG MỞ: Không có vị thế nào đang mở (0 Open Positions)")

    # Retrieve full history deals
    utc_now = datetime.now(timezone.utc)
    from_date_all = utc_now - timedelta(days=90)
    deals = mt5.history_deals_get(from_date_all, utc_now)

    if deals is None or len(deals) == 0:
        print("\nKhông tìm thấy dữ liệu giao dịch trong lịch sử.")
        mt5.shutdown()
        return

    df_deals = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    df_deals['time_dt'] = pd.to_datetime(df_deals['time'], unit='s', utc=True)
    df_deals['profit_total'] = df_deals['profit'] + df_deals['commission'] + df_deals['swap']

    # Dates
    today_start = utc_now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    mon_start = today_start - timedelta(days=today_start.weekday())

    def get_pnl_stats(df_sub, name):
        out_sub = df_sub[df_sub['entry'] == 1]
        closed_count = len(out_sub)
        gross_profit = df_sub['profit'].sum()
        commissions = df_sub['commission'].sum()
        swaps = df_sub['swap'].sum()
        net_pnl = gross_profit + commissions + swaps

        wins = out_sub[out_sub['profit_total'] > 0]
        losses = out_sub[out_sub['profit_total'] <= 0]
        win_rate = (len(wins) / closed_count * 100) if closed_count > 0 else 0.0
        
        gross_win = wins['profit_total'].sum() if len(wins) > 0 else 0.0
        gross_loss = losses['profit_total'].sum() if len(losses) > 0 else 0.0
        profit_factor = abs(gross_win / gross_loss) if gross_loss != 0 else (999.0 if gross_win > 0 else 0.0)

        return {
            'period': name,
            'closed': closed_count,
            'gross_pnl': gross_profit,
            'commissions': commissions,
            'swaps': swaps,
            'net_pnl': net_pnl,
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': win_rate,
            'profit_factor': profit_factor
        }

    stats_today = get_pnl_stats(df_deals[df_deals['time_dt'] >= today_start], f"Hôm nay ({today_start.strftime('%Y-%m-%d')})")
    stats_yesterday = get_pnl_stats(df_deals[(df_deals['time_dt'] >= yesterday_start) & (df_deals['time_dt'] < today_start)], f"Hôm qua ({yesterday_start.strftime('%Y-%m-%d')})")
    stats_week = get_pnl_stats(df_deals[df_deals['time_dt'] >= mon_start], f"Tuần này (Từ {mon_start.strftime('%Y-%m-%d')})")

    print("\n==================================================================")
    print("📈 TỔNG HỢP PNL CHI TIẾT")
    print("==================================================================")
    for st in [stats_today, stats_yesterday, stats_week]:
        print(f"📌 {st['period']}:")
        print(f"   • Số lệnh đóng:    {st['closed']} lệnh ({st['wins']} Thắng / {st['losses']} Thua | Win Rate: {st['win_rate']:.1f}%)")
        print(f"   • Gross PnL:       ${st['gross_pnl']:+.2f}")
        print(f"   • Phí (Comm+Swap): ${st['commissions'] + st['swaps']:+.2f}")
        print(f"   • Net PnL:         ${st['net_pnl']:+.2f}")
        print(f"   • Profit Factor:   {st['profit_factor']:.2f}")
        print("------------------------------------------------------------------")

    mt5.shutdown()

if __name__ == "__main__":
    main()
