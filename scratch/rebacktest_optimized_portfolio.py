import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from pathlib import Path

# Add workspace root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from v9_continuum.backtest import V9ContinuumBacktester

def analyze_weekly_pnl_custom(trades_df: pd.DataFrame, initial_bal=10000.0):
    df = trades_df.copy()
    df['close_time'] = pd.to_datetime(df['exit_time'])
    df = df.sort_values('close_time')
    df['week'] = df['close_time'].dt.to_period('W-SUN')

    weekly_summary = []
    running_balance = initial_bal

    for week, group in df.groupby('week'):
        net_pnl = group['profit'].sum()
        total_trades = len(group)
        winning_trades = len(group[group['profit'] > 0])
        losing_trades = len(group[group['profit'] < 0])

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

        gross_profit = group[group['profit'] > 0]['profit'].sum()
        gross_loss = abs(group[group['profit'] < 0]['profit'].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else gross_profit

        # Max Drawdown within the week
        group['cum_pnl'] = group['profit'].cumsum()
        group['peak'] = group['cum_pnl'].cummax()
        group['dd'] = group['peak'] - group['cum_pnl']
        max_weekly_dd = group['dd'].max()

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
    losing_weeks = report_df[report_df['Net_PnL ($)'] < 0]
    winning_weeks = report_df[report_df['Net_PnL ($)'] > 0]
    total_weeks = len(report_df)

    print('===========================================================')
    print('📊 BÁO CÁO KIỂM SOÁT HỆ THỐNG CUSTOM PORTFOLIO (18 THÁNG)')
    print('===========================================================')
    print(f'Tổng số tuần giao dịch  : {total_weeks} tuần')
    print(f'Số tuần thắng (Green)   : {len(winning_weeks)} ({len(winning_weeks)/total_weeks*100:.1f}%)')
    print(f'Số tuần thua (Red)     : {len(losing_weeks)} ({len(losing_weeks)/total_weeks*100:.1f}%)')
    print(f'Lợi nhuận tuần TB       : ${report_df["Net_PnL ($)"].mean():.2f}')
    
    max_win_idx = report_df["Net_PnL ($)"].idxmax()
    max_loss_idx = report_df["Net_PnL ($)"].idxmin()
    
    print(f'Tuần thắng lớn nhất     : ${report_df.loc[max_win_idx, "Net_PnL ($)"]:.2f} (Week {report_df.loc[max_win_idx, "Week"]})')
    print(f'Tuần thua lớn nhất      : ${report_df.loc[max_loss_idx, "Net_PnL ($)"]:.2f} (Week {report_df.loc[max_loss_idx, "Week"]})')
    print(f'Max Weekly Drawdown     : ${report_df["Max_Weekly_DD ($)"].max():.2f}')
    print('-----------------------------------------------------------')

    # Calculate 4 Red Flags
    # 1. Consecutive losing weeks
    is_loss = (report_df['Net_PnL ($)'] < 0).astype(int)
    consec_losses = is_loss.groupby((is_loss != is_loss.shift()).cumsum()).cumsum()
    max_consec_losses = consec_losses.max()

    max_weekly_dd_val = report_df["Max_Weekly_DD ($)"].max()
    max_weekly_dd_pct = (max_weekly_dd_val / initial_bal) * 100

    total_net_profit = report_df["Net_PnL ($)"].sum()
    best_week_pnl = report_df["Net_PnL ($)"].max()
    best_week_pct_of_total = (best_week_pnl / total_net_profit * 100) if total_net_profit > 0 else 0.0

    high_winrate_weeks = len(report_df[report_df['Win_Rate (%)'] >= 55.0])
    high_winrate_pct = (high_winrate_weeks / total_weeks * 100) if total_weeks > 0 else 0.0

    print("\n🎯 PHÂN TÍCH 4 THẺ BÀN KIỂM SOÁT (RED FLAGS AUDIT):")
    print("-----------------------------------------------------------")
    print(f"1. Chuỗi tuần thua liên tiếp max : {max_consec_losses} tuần (Target: <= 2-3 tuần) -> {'PASS 🟢' if max_consec_losses <= 3 else 'WARNING 🔴'}")
    print(f"2. Sụt giảm tuần tệ nhất (DD)    : ${max_weekly_dd_val:.2f} ({max_weekly_dd_pct:.2f}%) (Target: < 3.5% / $350) -> {'PASS 🟢' if max_weekly_dd_val < 350 else 'WARNING 🔴'}")
    print(f"3. Tỷ trọng tuần thắng lớn nhất  : {best_week_pct_of_total:.2f}% tổng lợi nhuận (Target: < 20%) -> {'PASS 🟢' if best_week_pct_of_total < 20 else 'WARNING 🔴'}")
    print(f"4. Tỷ lệ số tuần Win Rate >= 55% : {high_winrate_pct:.1f}% số tuần ({high_winrate_weeks}/{total_weeks}) (Target: >= 80%) -> {'PASS 🟢' if high_winrate_pct >= 80 else 'INFO 🟡'}")
    print("===========================================================\n")

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    # Run ONLY XAUUSD and US100 with ML veto threshold 0.80
    tester = V9ContinuumBacktester(ml_veto_threshold=0.80)
    symbols = ["XAUUSD", "US100"]
    
    start_date = datetime(2025, 6, 2, tzinfo=timezone.utc)
    end_date = datetime(2026, 6, 18, tzinfo=timezone.utc)
    
    print("Running backtest for XAUUSD & US100 Portfolio with ML Veto = 0.80...")
    portfolio, metrics = tester.run(symbols, start_date, end_date, initial_balance=10000.0)
    
    trades = []
    for c in portfolio.closed_cycles:
        trades.append({
            'symbol': c['symbol'],
            'profit': c['final_pnl'],
            'exit_time': c['exit_time']
        })
        
    if not trades:
        print("No trades generated.")
        return
        
    trades_df = pd.DataFrame(trades)
    analyze_weekly_pnl_custom(trades_df, initial_bal=10000.0)

if __name__ == '__main__':
    main()
