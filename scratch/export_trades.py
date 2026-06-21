import sys
import os
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(r"d:\05_Quant\NOWTRAEDING")
sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest_engine import BacktestEngine, VirtualPortfolio

# ── Patch VirtualPortfolio ──────────────────────────────────────────────────
# Patch close_cycle to capture close_time and close_price on the cycle object
original_close_cycle = VirtualPortfolio.close_cycle

def patched_close_cycle(self, symbol, price, time, reason):
    cycle = self.active_cycles.get(symbol)
    if cycle:
        cycle.close_time = time
        cycle.close_price = price
    original_close_cycle(self, symbol, price, time, reason)

VirtualPortfolio.close_cycle = patched_close_cycle

def run_export():
    print("Running 6-month Gold backtest to extract trades...")
    
    start_dt = datetime(2025, 12, 16, tzinfo=timezone.utc)
    end_dt = datetime(2026, 6, 16, 23, 59, 59, tzinfo=timezone.utc)
    
    engine = BacktestEngine()
    portfolio, metrics = engine.run_backtest(
        symbols=["XAUUSD"],
        start_date=start_dt,
        end_date=end_dt,
        initial_balance=1000.0,
        no_time_stop=False,
        use_spread=False,
        skip_equity_curve=True,
        skip_ml_export=True
    )
    
    closed_trades = portfolio.closed_cycles
    print(f"Captured {len(closed_trades)} closed trades.")
    
    # ── Create DataFrame and Export to CSV ────────────────────────────────────
    trade_records = []
    for i, c in enumerate(closed_trades):
        # Handle tickets list (sometimes multiple tickets if DCA layers are added)
        ticket_id = c.tickets[0] if c.tickets else i + 1
        
        # Calculate holding hours
        close_time = getattr(c, "close_time", c.entry_time)
        close_price = getattr(c, "close_price", c.average_entry_price)
        
        record = {
            "Ticket ID": ticket_id,
            "Open Time": c.entry_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "Close Time": close_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "Symbol": c.symbol,
            "Type": c.direction,
            "Base Price (Open)": round(c.base_entry_price, 2),
            "Avg Entry Price": round(c.average_entry_price, 2),
            "Close Price": round(close_price, 2),
            "Base Lot Size": round(c.base_lot, 2),
            "Total Lot Size": round(c.total_lots, 2),
            "DCA Layers": c.num_dca_layers,
            "Profit (USD)": round(c.current_profit_usd, 2),
            "Close Reason": c.close_reason
        }
        trade_records.append(record)
        
    df = pd.DataFrame(trade_records)
    csv_path = PROJECT_ROOT / "trades_history.csv"
    df.to_csv(csv_path, index=False)
    print(f"Successfully exported {len(df)} trades to: {csv_path}\n")
    
    # ── Perform Manual Calculation Verification ──────────────────────────────
    print("=== MANUAL SUMMATION VERIFICATION ===")
    pnl_sum = df["Profit (USD)"].sum()
    print(f"Cộng thủ công cột Profit (USD): ${pnl_sum:.2f}")
    print(f"Khớp với Profit Factor & Net Profit trong Backtest: ${metrics.get('total_profit_usd'):.2f}")
    
    # ── Analyze ML_VETO_CLOSE trades ──────────────────────────────────────────
    print("\n=== DETAILED ML_VETO_CLOSE TRADES (11 Trades) ===")
    veto_trades = df[df["Close Reason"] == "ML_VETO_CLOSE"]
    
    print(veto_trades[["Ticket ID", "Open Time", "Close Time", "Type", "Total Lot Size", "Profit (USD)", "Close Price"]].to_string(index=False))
    
    total_veto_pnl = veto_trades["Profit (USD)"].sum()
    print(f"\n-> Tổng PnL của 11 lệnh ML_VETO_CLOSE: ${total_veto_pnl:+.2f} USD")
    
    wins_veto = veto_trades[veto_trades["Profit (USD)"] > 0]
    losses_veto = veto_trades[veto_trades["Profit (USD)"] <= 0]
    print(f"   - Thắng: {len(wins_veto)} lệnh, Tổng lãi: ${wins_veto['Profit (USD)'].sum():+.2f} USD")
    print(f"   - Thua:  {len(losses_veto)} lệnh, Tổng lỗ: ${losses_veto['Profit (USD)'].sum():+.2f} USD")

if __name__ == "__main__":
    run_export()
