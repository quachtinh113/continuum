import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone

# Add workspace root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from v9_continuum.backtest import V9ContinuumBacktester

def analyze_weekly_pnl_18m(trades_df: pd.DataFrame):
    """
    Phân tích PnL 18 tháng (78 tuần) để kiểm soát hệ thống V9 Continuum.
    trades_df yêu cầu các cột: ['close_time', 'symbol', 'profit', 'initial_balance']
    """
    df = trades_df.copy()
    df['close_time'] = pd.to_datetime(df['close_time'])
    df = df.sort_values('close_time')

    # Gom nhóm theo tuần (Thứ Hai làm ngày đầu tuần)
    df['week'] = df['close_time'].dt.to_period('W-SUN')

    weekly_summary = []
    running_balance = (
        df['initial_balance'].iloc[0] if 'initial_balance' in df and len(df) > 0 else 10000.0
    )

    for week, group in df.groupby('week'):
        net_pnl = group['profit'].sum()
        total_trades = len(group)
        winning_trades = len(group[group['profit'] > 0])
        losing_trades = len(group[group['profit'] < 0])

        win_rate = (
            (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        )

        gross_profit = group[group['profit'] > 0]['profit'].sum()
        gross_loss = abs(group[group['profit'] < 0]['profit'].sum())
        profit_factor = (
            (gross_profit / gross_loss) if gross_loss > 0 else gross_profit
        )

        # Max Drawdown trong tuần
        group['cum_pnl'] = group['profit'].cumsum()
        group['peak'] = group['cum_pnl'].cummax()
        group['dd'] = group['peak'] - group['cum_pnl']
        max_weekly_dd = group['dd'].max()

        # % Tăng trưởng tuần
        week_start_bal = running_balance
        running_balance += net_pnl
        return_pct = (net_pnl / week_start_bal) * 100 if week_start_bal > 0 else 0.0

        weekly_summary.append({
            'Week': str(week),
            'Start_Date': group['close_time'].min().strftime('%Y-%m-%d'),
            'End_Date': group['close_time'].max().strftime('%Y-%m-%d'),
            'Net_PnL ($)': round(net_pnl, 2),
            'Return (%)': round(return_pct, 2),
            'Trades': total_trades,
            'Win_Rate (%)': round(win_rate, 2),
            'Profit_Factor': round(profit_factor, 2),
            'Max_Weekly_DD ($)': round(max_weekly_dd, 2),
            'End_Balance ($)': round(running_balance, 2),
        })

    report_df = pd.DataFrame(weekly_summary)

    # Ensure logs dir exists
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # 📊 XUẤT THỐNG KÊ TỔNG QUAN HỆ THỐNG
    losing_weeks = report_df[report_df['Net_PnL ($)'] < 0]
    winning_weeks = report_df[report_df['Net_PnL ($)'] > 0]
    total_weeks = len(report_df)

    print('===========================================================')
    print('📊 BÁO CÁO KIỂM SOÁT HỆ THỐNG V9 CONTINUUM (18 THÁNG / 78 TUẦN)')
    print('===========================================================')
    print(f'Tổng số tuần giao dịch  : {total_weeks} tuần')
    print(
        f'Số tuần thắng (Green)   : {len(winning_weeks)} ({len(winning_weeks)/total_weeks*100:.1f}%)'
    )
    print(
        f'Số tuần thua (Red)     : {len(losing_weeks)} ({len(losing_weeks)/total_weeks*100:.1f}%)'
    )
    print(f'Lợi nhuận tuần TB       : ${report_df["Net_PnL ($)"].mean():.2f}')
    
    max_win_idx = report_df["Net_PnL ($)"].idxmax()
    max_loss_idx = report_df["Net_PnL ($)"].idxmin()
    
    print(
        f'Tuần thắng lớn nhất     : ${report_df.loc[max_win_idx, "Net_PnL ($)"]:.2f} (Week {report_df.loc[max_win_idx, "Week"]})'
    )
    print(
        f'Tuần thua lớn nhất      : ${report_df.loc[max_loss_idx, "Net_PnL ($)"]:.2f} (Week {report_df.loc[max_loss_idx, "Week"]})'
    )
    print(
        f'Max Weekly Drawdown     : ${report_df["Max_Weekly_DD ($)"].max():.2f}'
    )
    print('-----------------------------------------------------------')

    # Calculate 4 Red Flags
    # 1. Consecutive losing weeks
    is_loss = (report_df['Net_PnL ($)'] < 0).astype(int)
    consec_losses = is_loss.groupby((is_loss != is_loss.shift()).cumsum()).cumsum()
    max_consec_losses = consec_losses.max()

    # 2. Worst weekly DD (% relative to initial $10k or weekly start)
    max_weekly_dd_val = report_df["Max_Weekly_DD ($)"].max()
    max_weekly_dd_pct = (max_weekly_dd_val / 10000.0) * 100

    # 3. Outlier check: Best week profit / Total Net Profit
    total_net_profit = report_df["Net_PnL ($)"].sum()
    best_week_pnl = report_df["Net_PnL ($)"].max()
    best_week_pct_of_total = (best_week_pnl / total_net_profit * 100) if total_net_profit > 0 else 0.0

    # 4. Weekly Win Rate >= 55% across % of weeks
    high_winrate_weeks = len(report_df[report_df['Win_Rate (%)'] >= 55.0])
    high_winrate_pct = (high_winrate_weeks / total_weeks * 100) if total_weeks > 0 else 0.0

    print("\n🎯 PHÂN TÍCH 4 THẺ BÀN KIỂM SOÁT (RED FLAGS AUDIT):")
    print("-----------------------------------------------------------")
    print(f"1. Chuỗi tuần thua liên tiếp max : {max_consec_losses} tuần (Target: <= 2-3 tuần) -> {'PASS 🟢' if max_consec_losses <= 3 else 'WARNING 🔴'}")
    print(f"2. Sụt giảm tuần tệ nhất (DD)    : ${max_weekly_dd_val:.2f} ({max_weekly_dd_pct:.2f}%) (Target: < 3.5% / $350) -> {'PASS 🟢' if max_weekly_dd_val < 350 else 'WARNING 🔴'}")
    print(f"3. Tỷ trọng tuần thắng lớn nhất  : {best_week_pct_of_total:.2f}% tổng lợi nhuận (Target: < 20%) -> {'PASS 🟢' if best_week_pct_of_total < 20 else 'WARNING 🔴'}")
    print(f"4. Tỷ lệ số tuần Win Rate >= 55% : {high_winrate_pct:.1f}% số tuần ({high_winrate_weeks}/{total_weeks}) (Target: >= 80%) -> {'PASS 🟢' if high_winrate_pct >= 80 else 'INFO 🟡'}")
    print("===========================================================\n")

    # Lưu kết quả file CSV
    csv_path = 'logs/pnl_18months_weekly.csv'
    report_df.to_csv(csv_path, index=False)
    print(f'✅ Chi tiết {total_weeks} tuần đã được lưu tại: {csv_path}')
    return report_df

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("Running V9 Continuum Backtest to extract 18-Month (78-Week) trade history...")
    
    tester = V9ContinuumBacktester()
    symbols_to_test = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "US100", "US500", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]
    
    available_symbols = []
    for s in symbols_to_test:
        if (Path("data/historical") / f"{s}_M15.csv").exists():
            available_symbols.append(s)
            
    start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2026, 7, 25, tzinfo=timezone.utc)
    
    print(f"Simulating trades from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} for {available_symbols}...")
    portfolio, metrics = tester.run(available_symbols, start_date, end_date, initial_balance=10000.0)
    
    trades = []
    for c in portfolio.closed_cycles:
        trades.append({
            'close_time': c['exit_time'],
            'symbol': c['symbol'],
            'profit': c['final_pnl'],
            'initial_balance': 10000.0
        })
        
    if not trades:
        print("No closed trades generated.")
        return

    trades_df = pd.DataFrame(trades)
    analyze_weekly_pnl_18m(trades_df)

if __name__ == '__main__':
    main()
