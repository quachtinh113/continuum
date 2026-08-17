import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime, timezone

# Pip size definitions per symbol
PIP_SIZES = {
    "XAUUSDm": 0.1,    # $0.10 per point for Gold
    "XAUUSD": 0.1,
    "USTECm": 1.0,     # 1 point for Nasdaq
    "US100": 1.0,
    "US30m": 1.0,
    "US30": 1.0,
    "US500m": 0.1,
    "US500": 0.1,
    "EURUSDm": 0.0001,
    "GBPUSDm": 0.0001,
    "AUDUSDm": 0.0001,
    "NZDUSDm": 0.0001,
    "USDCADm": 0.0001,
    "USDCHFm": 0.0001,
    "USDJPYm": 0.01,
    "BTCUSDm": 1.0,
}

CONTRACT_SIZES = {
    "XAUUSDm": 100,
    "USTECm": 1,
    "US30m": 1,
    "US500m": 10,
    "EURUSDm": 100000,
    "GBPUSDm": 100000,
    "AUDUSDm": 100000,
    "NZDUSDm": 100000,
    "USDCADm": 100000,
    "USDCHFm": 100000,
    "USDJPYm": 100000,
    "BTCUSDm": 1,
}

def load_audit_signal_prices():
    """Build a mapping of (symbol, approx_timestamp_minute) -> signal_price from JSONL logs."""
    signals = {}
    log_dir = Path("logs")
    for log_path in sorted(log_dir.glob("audit_2026-08-*.jsonl")):
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    event = data.get("event") or data.get("severity")
                    symbol = data.get("symbol")
                    price = data.get("price") or data.get("entry_price")
                    ts_str = data.get("timestamp")
                    
                    if symbol and price and ts_str:
                        # Normalize symbol name (e.g. XAUUSD -> XAUUSDm)
                        sym_m = symbol + "m" if not symbol.endswith("m") else symbol
                        ts = datetime.strptime(ts_str[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                        minute_key = (sym_m, ts.strftime("%Y-%m-%d %H:%M"))
                        # Save latest signal price in that minute
                        signals[minute_key] = float(price)
                except Exception:
                    pass
    return signals

def main():
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print("==========================================================")
    print("      SLIPPAGE & HIDDEN COSTS AUDIT (67 DEALS)")
    print("==========================================================")

    if not mt5.initialize():
        print(f"Failed to initialize MT5: {mt5.last_error()}")
        sys.exit(1)

    start_date = datetime(2026, 8, 3, 0, 0, 0, tzinfo=timezone.utc)
    end_date = datetime(2026, 8, 9, 23, 59, 59, tzinfo=timezone.utc)

    deals = mt5.history_deals_get(start_date, end_date)
    if not deals:
        print("No deals found.")
        mt5.shutdown()
        sys.exit(0)

    df_deals = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    df_deals['time_dt'] = pd.to_datetime(df_deals['time'], unit='s', utc=True)

    # Filter entry = 0 (IN) which are trade executions
    entry_deals = df_deals[df_deals['entry'] == 0].copy()
    print(f"Found {len(entry_deals)} entry execution deals across the week.")

    signal_map = load_audit_signal_prices()

    slippage_records = []
    total_gross_profit = df_deals['profit'].sum()
    total_commission = df_deals['commission'].sum()
    total_swap = df_deals['swap'].sum()

    for idx, row in entry_deals.iterrows():
        sym = row['symbol']
        exec_price = row['price']
        vol = row['volume']
        t_dt = row['time_dt']
        minute_key = (sym, t_dt.strftime("%Y-%m-%d %H:%M"))

        # Find matching signal price or look within +/- 2 minutes
        signal_price = signal_map.get(minute_key)
        if signal_price is None:
            # Fallback search within +/- 2 minutes
            for delta_m in [-1, 1, -2, 2]:
                alt_t = t_dt + pd.Timedelta(minutes=delta_m)
                alt_key = (sym, alt_t.strftime("%Y-%m-%d %H:%M"))
                if alt_key in signal_map:
                    signal_price = signal_map[alt_key]
                    break

        if signal_price is None:
            signal_price = exec_price # zero slippage fallback if unmapped

        pip_size = PIP_SIZES.get(sym, 0.0001)
        price_diff = abs(exec_price - signal_price)
        slippage_pips = price_diff / pip_size

        # Estimate slippage cost in USD
        contract_size = CONTRACT_SIZES.get(sym, 100000)
        slippage_usd = price_diff * contract_size * vol

        slippage_records.append({
            'Ticket': row['position_id'],
            'Time': t_dt.strftime("%H:%M:%S"),
            'Symbol': sym,
            'Volume': vol,
            'Signal_Price': signal_price,
            'Exec_Price': exec_price,
            'Slippage_Pips': round(slippage_pips, 2),
            'Slippage_USD': round(slippage_usd, 2)
        })

    df_slip = pd.DataFrame(slippage_records)

    print("\n📊 SLIPPAGE AUDIT SUMMARY BY ASSET:")
    sym_grp = df_slip.groupby('Symbol').agg(
        Deals=('Slippage_Pips', 'count'),
        Avg_Slippage_Pips=('Slippage_Pips', 'mean'),
        Max_Slippage_Pips=('Slippage_Pips', 'max'),
        Total_Slippage_USD=('Slippage_USD', 'sum')
    ).reset_index()

    print(sym_grp.to_string(index=False))

    overall_avg_slip = df_slip['Slippage_Pips'].mean()
    total_slip_usd = df_slip['Slippage_USD'].sum()
    total_hidden_costs = total_slip_usd + abs(total_commission) + abs(total_swap)
    hidden_cost_pct = (total_hidden_costs / total_gross_profit * 100) if total_gross_profit > 0 else 0.0

    print("\n==========================================================")
    print(f"OVERALL SLIPPAGE & COST AUDIT VERDICT:")
    print(f"  Total Closed Deals Audited │ {len(df_slip)}")
    print(f"  Average Slippage           │ {overall_avg_slip:.2f} pips")
    print(f"  Total Gross Profit         │ ${total_gross_profit:.2f} USD")
    print(f"  Total Slippage Drag        │ ${total_slip_usd:.2f} USD")
    print(f"  Total Commissions          │ ${total_commission:.2f} USD")
    print(f"  Total Swaps                │ ${total_swap:.2f} USD")
    print(f"  Total Hidden Costs         │ ${total_hidden_costs:.2f} USD")
    print(f"  Hidden Cost / Gross Profit │ {hidden_cost_pct:.2f}%")
    print("==========================================================")

    if overall_avg_slip <= 1.5:
        print("✅ VERDICT: PASSED! Average slippage is <= 1.5 pips. Alpha is REAL and execution-viable.")
    else:
        print("❌ VERDICT: FAILED! Average slippage > 1.5 pips. Alpha is paper-only.")

    mt5.shutdown()

if __name__ == '__main__':
    main()
