import pandas as pd
import sys

def calculate_drawdown_from_csv(csv_path: str, initial_balance: float = 10000.0):
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"File not found: {csv_path}")
        return

    if 'profit_usd' not in df.columns or 'entry_time' not in df.columns:
        print("Required columns ('profit_usd', 'entry_time') not found in CSV.")
        return

    # Ensure chronological order
    df['entry_time'] = pd.to_datetime(df['entry_time'])
    df = df.sort_values('entry_time')

    balance = initial_balance
    peak_balance = initial_balance
    max_drawdown_usd = 0.0
    max_drawdown_pct = 0.0

    print("--- INDEPENDENT DRAWDOWN CALCULATION ---")
    print(f"Initial Balance: ${initial_balance:,.2f}")
    
    for idx, row in df.iterrows():
        profit = row['profit_usd']
        balance += profit
        
        if balance > peak_balance:
            peak_balance = balance
            
        drawdown_usd = peak_balance - balance
        drawdown_pct = drawdown_usd / peak_balance if peak_balance > 0 else 0
        
        if drawdown_usd > max_drawdown_usd:
            max_drawdown_usd = drawdown_usd
        if drawdown_pct > max_drawdown_pct:
            max_drawdown_pct = drawdown_pct

    print(f"Final Balance: ${balance:,.2f}")
    print(f"Total Trades: {len(df)}")
    print(f"Peak Balance: ${peak_balance:,.2f}")
    print(f"Max Closed Drawdown (USD): ${max_drawdown_usd:,.2f}")
    print(f"Max Closed Drawdown (%): {max_drawdown_pct * 100:.2f}%")

if __name__ == "__main__":
    calculate_drawdown_from_csv("raw_trade_list.csv")
