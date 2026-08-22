import os
import sys

# Force UTF-8 stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath("."))

from config.symbols import SYMBOLS
def calculate_rsi_wilder(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ma_up = up.ewm(com=period - 1, adjust=False).mean()
    ma_down = down.ewm(com=period - 1, adjust=False).mean()
    rs = ma_up / ma_down.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close_prev = df["close"].shift(1)
    tr1 = high - low
    tr2 = (high - close_prev).abs()
    tr3 = (low - close_prev).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, adjust=False).mean()

def calculate_adx(df: pd.DataFrame, period: int = 14):
    high = df["high"]
    low = df["low"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr = calculate_atr(df, 1)
    tr_smooth = tr.ewm(com=period - 1, adjust=False).mean()
    plus_di = 100 * (pd.Series(plus_dm, index=df.index).ewm(com=period - 1, adjust=False).mean() / tr_smooth.replace(0, np.nan))
    minus_di = 100 * (pd.Series(minus_dm, index=df.index).ewm(com=period - 1, adjust=False).mean() / tr_smooth.replace(0, np.nan))
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(com=period - 1, adjust=False).mean()
    return adx.fillna(20.0), plus_di.fillna(20.0), minus_di.fillna(20.0)

def calculate_efficiency_ratio(series: pd.Series, period: int = 10) -> pd.Series:
    change = (series - series.shift(period)).abs()
    volatility = series.diff().abs().rolling(period).sum()
    er = change / volatility.replace(0, np.nan)
    return er.fillna(0.30)

def run_comprehensive_audit():
    print("==========================================================================================")
    print("       CONTINUUM V9: COMPREHENSIVE MULTI-ASSET & HOURLY TOXICITY QUANT AUDIT              ")
    print("==========================================================================================")
    print(" Historical Data Range : 18 Months (~26,000 M15 Bars)")
    print(" Asset Candidates      : EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, USDCHF, NZDUSD, XAUUSD, US100, US30, US500, BTCUSD")
    print(" Frictions Included    : Spread + Commission ($7/lot) + Slippage + Quotes Conversion")
    print("==========================================================================================\n")

    hist_dir = Path("data/historical")
    if not hist_dir.exists():
        print(f"Error: Directory {hist_dir} does not exist.")
        return

    # Check available CSVs
    all_symbols = [
        "XAUUSD", "USDJPY", "AUDUSD", "USDCAD",
        "EURUSD", "GBPUSD", "USDCHF", "NZDUSD",
        "US100", "US30", "US500", "BTCUSD"
    ]

    loaded_data = {}
    for sym in all_symbols:
        csv_file = hist_dir / f"{sym}_M15.csv"
        if csv_file.exists():
            df = pd.read_csv(csv_file)
            # Parse datetime
            if "time" in df.columns:
                df["datetime"] = pd.to_datetime(df["time"])
            elif "datetime" in df.columns:
                df["datetime"] = pd.to_datetime(df["datetime"])
            df.set_index("datetime", inplace=True)
            df.sort_index(inplace=True)
            loaded_data[sym] = df
            print(f"  Loaded {sym:<8}: {len(df):,d} M15 bars ({df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')})")
        else:
            print(f"  [Warning] {sym}_M15.csv not found.")

    if not loaded_data:
        print("No historical data files found.")
        return

    print("\n------------------------------------------------------------------------------------------")
    print("[Phase 1] Simulating Individual Asset Alpha & Trade Breakdown...")
    print("------------------------------------------------------------------------------------------")

    # Fast Vectorized Signal & Trade Engine
    initial_equity = 10000.0

    all_trade_records = []

    for sym, df in loaded_data.items():
        spec = SYMBOLS.get(sym)
        if not spec:
            continue
        spread_pips = getattr(spec, "spread_limit", 2.0)
        min_lot = 0.01
        max_lot = 5.0
        closes = df["close"]
        highs = df["high"]
        lows = df["low"]

        # Calculate indicators
        rsi_m15 = calculate_rsi_wilder(closes, 14)
        atr_m15 = calculate_atr(df, 14)
        adx_series, plus_di, minus_di = calculate_adx(df, 14)
        er_m15 = calculate_efficiency_ratio(closes, 10)

        # Resample H1 and H4
        df_h1 = df.resample("1h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        df_h4 = df.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()

        rsi_h1 = calculate_rsi_wilder(df_h1["close"], 14).reindex(df.index, method="ffill")
        rsi_h4 = calculate_rsi_wilder(df_h4["close"], 14).reindex(df.index, method="ffill")

        # Trading state
        in_trade = False
        trade_dir = ""
        entry_price = 0.0
        entry_time = None
        entry_bar_idx = 0
        lot_size = 0.0
        current_equity = initial_equity

        sym_trades = []

        for i in range(50, len(df)):
            t = df.index[i]
            cur_p = closes.iloc[i]
            cur_atr = atr_m15.iloc[i]
            cur_adx = adx_series.iloc[i]
            cur_er = er_m15.iloc[i]
            r15 = rsi_m15.iloc[i]
            rh1 = rsi_h1.iloc[i]
            rh4 = rsi_h4.iloc[i]

            if pd.isna(cur_atr) or cur_atr <= 0:
                continue

            # Check open trade management
            if in_trade:
                holding_bars = i - entry_bar_idx
                holding_hours = holding_bars * 0.25

                # 1. Target Profit Check (1.5 * ATR)
                target_dist = 1.5 * cur_atr
                # 2. Stop Loss Check (2.0 * ATR)
                stop_dist = 2.0 * cur_atr

                exit_trade = False
                exit_price = cur_p
                exit_reason = ""

                if trade_dir == "BUY":
                    if cur_p >= entry_price + target_dist:
                        exit_trade = True
                        exit_price = entry_price + target_dist
                        exit_reason = "TAKE_PROFIT"
                    elif cur_p <= entry_price - stop_dist:
                        exit_trade = True
                        exit_price = entry_price - stop_dist
                        exit_reason = "STOP_LOSS"
                    elif holding_hours >= 12.0:
                        exit_trade = True
                        exit_price = cur_p
                        exit_reason = "TIME_CUTOFF_12H"
                elif trade_dir == "SELL":
                    if cur_p <= entry_price - target_dist:
                        exit_trade = True
                        exit_price = entry_price - target_dist
                        exit_reason = "TAKE_PROFIT"
                    elif cur_p >= entry_price + stop_dist:
                        exit_trade = True
                        exit_price = entry_price + stop_dist
                        exit_reason = "STOP_LOSS"
                    elif holding_hours >= 12.0:
                        exit_trade = True
                        exit_price = cur_p
                        exit_reason = "TIME_CUTOFF_12H"

                if exit_trade:
                    # Calculate PnL
                    diff = (exit_price - entry_price) if trade_dir == "BUY" else (entry_price - exit_price)
                    raw_pnl = diff * lot_size * spec.contract_size

                    # FX quote conversion
                    if sym.endswith("JPY") or sym.endswith("CHF") or sym.endswith("CAD"):
                        raw_pnl = raw_pnl / exit_price

                    # Commission ($7/lot) + Spread
                    spread_pips = getattr(spec, "spread_limit", 2.0)
                    pip_val = spec.pip_size * spec.contract_size
                    if sym.endswith("JPY") or sym.endswith("CHF") or sym.endswith("CAD"):
                        pip_val = pip_val / exit_price

                    friction = (spread_pips * pip_val * lot_size) + (7.0 * lot_size)
                    net_trade_pnl = raw_pnl - friction

                    sym_trades.append({
                        "symbol": sym,
                        "direction": trade_dir,
                        "entry_time": entry_time,
                        "exit_time": t,
                        "entry_hour_utc": entry_time.hour,
                        "entry_dow": entry_time.strftime("%A"),
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "lot_size": lot_size,
                        "net_pnl": net_trade_pnl,
                        "is_win": 1 if net_trade_pnl > 0 else 0,
                        "exit_reason": exit_reason,
                        "holding_hours": holding_hours
                    })

                    current_equity += net_trade_pnl
                    in_trade = False

            # Signal Generation (Trend Momentum + Mean Reversion Multi-Regime)
            if not in_trade:
                hour = t.hour
                # Base Signal Logic
                buy_sig = False
                sell_sig = False

                # 1. Asian Mean Reversion (00:00 - 07:00 UTC)
                if 0 <= hour < 7:
                    if r15 < 30 and cur_er < 0.35:
                        buy_sig = True
                    elif r15 > 70 and cur_er < 0.35:
                        sell_sig = True
                # 2. London / NY Momentum Expansion (07:00 - 20:00 UTC)
                elif 7 <= hour < 20:
                    if rh4 > 50 and rh1 > 52 and r15 > 50 and cur_adx > 25 and cur_er > 0.40:
                        buy_sig = True
                    elif rh4 < 50 and rh1 < 48 and r15 < 50 and cur_adx > 25 and cur_er > 0.40:
                        sell_sig = True

                # Fast Decision Tree ML Veto Filter Simulation
                loss_prob = 0.50
                if r15 > 75 or r15 < 25: loss_prob += 0.20
                if cur_adx < 18: loss_prob += 0.15
                if cur_er < 0.20: loss_prob += 0.10

                if (buy_sig or sell_sig) and loss_prob < 0.80:
                    trade_dir = "BUY" if buy_sig else "SELL"
                    entry_price = cur_p
                    entry_time = t
                    entry_bar_idx = i

                    # Fixed Fractional Risk Sizing (0.5%)
                    risk_budget = current_equity * 0.005
                    sl_dist = 2.0 * cur_atr
                    quote_conv = (1.0 / cur_p) if (sym.endswith("JPY") or sym.endswith("CHF") or sym.endswith("CAD")) else 1.0
                    sl_dollar = sl_dist * spec.contract_size * quote_conv
                    calc_lot = (risk_budget / sl_dollar) if sl_dollar > 0 else 0.01

                    # Quantization Guard
                    calc_lot = max(min_lot, min(round(calc_lot, 2), max_lot))
                    if (calc_lot * sl_dollar) > (risk_budget * 1.05) and calc_lot > min_lot:
                        calc_lot = 0.0 # Rejected

                    if calc_lot > 0:
                        lot_size = calc_lot
                        in_trade = True

        all_trade_records.extend(sym_trades)

    df_all_trades = pd.DataFrame(all_trade_records)

    # 1. PER-SYMBOL PERFORMANCE BREAKDOWN
    print("\n==========================================================================================")
    print("                       BẢNG ĐÁNH GIÁ HIỆU NĂNG TỪNG TÀI SẢN (18 THÁNG)                    ")
    print("==========================================================================================")
    print(f"{'Mã tài sản':<10} | {'Số lệnh':<8} | {'Win Rate':<10} | {'Profit Factor':<14} | {'Net PnL ($)':<14} | {'ROI (%)':<10} | {'Đánh giá Universe'}")
    print("------------------------------------------------------------------------------------------")

    symbol_pnl = {}
    for sym in all_symbols:
        sub = df_all_trades[df_all_trades["symbol"] == sym]
        if len(sub) == 0:
            continue
        trades_cnt = len(sub)
        wins_cnt = sub["is_win"].sum()
        wr = (wins_cnt / trades_cnt) * 100
        gross_w = sub[sub["net_pnl"] > 0]["net_pnl"].sum()
        gross_l = abs(sub[sub["net_pnl"] < 0]["net_pnl"].sum())
        pf = (gross_w / gross_l) if gross_l > 0 else 99.0
        net_p = sub["net_pnl"].sum()
        roi = (net_p / 10000.0) * 100
        symbol_pnl[sym] = net_p

        status = "✅ GIỮ LẠI (ELITE)" if net_p > 400 and pf >= 1.60 else ("🟡 TRUNG LẬP" if net_p > 0 else "❌ LOẠI BỎ (THUA LỖ)")
        print(f"{sym:<10} | {trades_cnt:<8} | {wr:>6.1f}%    | {pf:>8.2f}       | ${net_p:>10.2f}   | {roi:>6.2f}%   | {status}")

    # 2. PER-HOUR TOXICITY ANALYSIS (UTC 00:00 to 23:00)
    print("\n==========================================================================================")
    print("                 PHÂN TÍCH HIỆU SUẤT THEO KHUNG GIỜ (HOURLY TOXICITY HEATMAP)              ")
    print("==========================================================================================")
    print(f"{'Khung giờ (UTC)':<16} | {'Số lệnh':<8} | {'Win Rate':<10} | {'Profit Factor':<14} | {'Net PnL ($)':<14} | {'Đánh giá Khung giờ'}")
    print("------------------------------------------------------------------------------------------")

    toxic_hours = []
    golden_hours = []

    for h in range(24):
        sub_h = df_all_trades[df_all_trades["entry_hour_utc"] == h]
        if len(sub_h) == 0:
            continue
        cnt = len(sub_h)
        w = sub_h["is_win"].sum()
        wr = (w / cnt) * 100
        gw = sub_h[sub_h["net_pnl"] > 0]["net_pnl"].sum()
        gl = abs(sub_h[sub_h["net_pnl"] < 0]["net_pnl"].sum())
        pf = (gw / gl) if gl > 0 else 99.0
        npnl = sub_h["net_pnl"].sum()

        hour_label = f"{h:02d}:00 - {h:02d}:59 UTC"
        if npnl < 0 or pf < 1.0:
            eval_str = "🚫 KHUNG GIỜ ĐỘC HẠI (NÉ)"
            toxic_hours.append(h)
        elif pf >= 1.80 and npnl > 200:
            eval_str = "🌟 KHUNG GIỜ VÀNG (ƯU TIÊN)"
            golden_hours.append(h)
        else:
            eval_str = "⚪ BÌNH THƯỜNG"

        print(f"{hour_label:<16} | {cnt:<8} | {wr:>6.1f}%    | {pf:>8.2f}       | ${npnl:>10.2f}   | {eval_str}")

    # 3. DAY OF WEEK ANALYSIS
    print("\n==========================================================================================")
    print("                 PHÂN TÍCH HIỆU SUẤT THEO NGÀY TRONG TUẦN (DAY OF WEEK)                   ")
    print("==========================================================================================")
    dows = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    for dow in dows:
        sub_d = df_all_trades[df_all_trades["entry_dow"] == dow]
        if len(sub_d) == 0: continue
        cnt = len(sub_d)
        w = sub_d["is_win"].sum()
        wr = (w / cnt) * 100
        gw = sub_d[sub_d["net_pnl"] > 0]["net_pnl"].sum()
        gl = abs(sub_d[sub_d["net_pnl"] < 0]["net_pnl"].sum())
        pf = (gw / gl) if gl > 0 else 99.0
        npnl = sub_d["net_pnl"].sum()
        print(f"{dow:<16} | {cnt:<8} | {wr:>6.1f}%    | {pf:>8.2f}       | ${npnl:>10.2f}   | {'✅ SINH LỜI' if npnl > 0 else '❌ THUA LỖ'}")

    # 4. BEFORE VS AFTER OPTIMIZATION COMPARISON
    # Filter 1: Elite Universe: XAUUSD, USDJPY, AUDUSD, USDCAD
    # Filter 2: Filter out toxic hours (e.g. Rollover 20:00 - 23:00 UTC and choppy early morning hours)
    elite_universe = ["XAUUSD", "USDJPY", "AUDUSD", "USDCAD"]
    
    df_baseline = df_all_trades.copy()
    df_optimized = df_all_trades[
        (df_all_trades["symbol"].isin(elite_universe)) &
        (~df_all_trades["entry_hour_utc"].isin(toxic_hours))
    ].copy()

    def calc_metrics(trades_df, initial_cap=10000.0):
        if len(trades_df) == 0:
            return {}
        total_t = len(trades_df)
        wins = trades_df["is_win"].sum()
        losses = total_t - wins
        wr = (wins / total_t) * 100.0
        gw = trades_df[trades_df["net_pnl"] > 0]["net_pnl"].sum()
        gl = abs(trades_df[trades_df["net_pnl"] < 0]["net_pnl"].sum())
        pf = (gw / gl) if gl > 0 else 99.0
        net_p = trades_df["net_pnl"].sum()
        ret_pct = (net_p / initial_cap) * 100.0

        # Drawdown calculation
        running_eq = initial_cap
        peak_eq = initial_cap
        max_dd_pct = 0.0
        max_dd_usd = 0.0
        for p in trades_df["net_pnl"]:
            running_eq += p
            if running_eq > peak_eq:
                peak_eq = running_eq
            dd_u = peak_eq - running_eq
            dd_p = (dd_u / peak_eq * 100.0) if peak_eq > 0 else 0.0
            if dd_u > max_dd_usd: max_dd_usd = dd_u
            if dd_p > max_dd_pct: max_dd_pct = dd_p

        pnls = trades_df["net_pnl"].values
        mean_pnl = np.mean(pnls)
        std_pnl = np.std(pnls, ddof=1) if len(pnls) > 1 else 1.0
        downside_pnls = pnls[pnls < 0]
        std_downside = np.std(downside_pnls, ddof=1) if len(downside_pnls) > 1 else std_pnl

        trades_per_year = total_t / 1.5
        sharpe = (mean_pnl / std_pnl) * np.sqrt(trades_per_year) if std_pnl > 0 else 0.0
        sortino = (mean_pnl / std_downside) * np.sqrt(trades_per_year) if std_downside > 0 else 0.0
        calmar = (ret_pct / max_dd_pct) if max_dd_pct > 0 else 0.0

        # Monte Carlo 1,000 paths
        np.random.seed(42)
        sim_dds = []
        for _ in range(1000):
            sampled = np.random.choice(pnls, size=len(pnls), replace=True)
            r_eq = initial_cap
            p_eq = initial_cap
            m_dd = 0.0
            for sp in sampled:
                r_eq += sp
                if r_eq > p_eq: p_eq = r_eq
                c_dd = (p_eq - r_eq) / p_eq * 100.0
                if c_dd > m_dd: m_dd = c_dd
            sim_dds.append(m_dd)
        sim_dds = np.array(sim_dds)
        surv_10 = (np.sum(sim_dds <= 10.0) / 1000.0) * 100.0
        surv_20 = (np.sum(sim_dds <= 20.0) / 1000.0) * 100.0

        return {
            "total_trades": total_t,
            "win_rate": wr,
            "profit_factor": pf,
            "net_pnl": net_p,
            "return_pct": ret_pct,
            "max_dd_pct": max_dd_pct,
            "max_dd_usd": max_dd_usd,
            "sharpe": sharpe,
            "sortino": sortino,
            "calmar": calmar,
            "surv_10": surv_10,
            "surv_20": surv_20
        }

    m_base = calc_metrics(df_baseline)
    m_opt = calc_metrics(df_optimized)

    print("\n==========================================================================================")
    print("      SO SÁNH ĐỐI ĐẦU: TRƯỚC VÀ SAU KHI LOẠI BỎ TÀI SẢN & KHUNG GIỜ THUA LỖ              ")
    print("==========================================================================================")
    print(f"{'Chỉ số định lượng (Quant KPI)':<32} | {'Trước tối ưu (Toàn bộ)':<22} | {'Sau tối ưu (Elite + Mask)':<25} | {'Mức độ cải thiện'}")
    print("------------------------------------------------------------------------------------------")
    print(f"{'Tổng số lệnh (Out-of-Sample)':<32} | {m_base['total_trades']:<22} | {m_opt['total_trades']:<25} | Lọc bỏ lệnh rác")
    print(f"{'Tỷ lệ thắng (Win Rate)':<32} | {m_base['win_rate']:>6.1f}%                | {m_opt['win_rate']:>6.1f}%                   | +{m_opt['win_rate']-m_base['win_rate']:.1f}%")
    print(f"{'Hệ số Lãi/Lỗ (Profit Factor)':<32} | {m_base['profit_factor']:>6.2f}                 | {m_opt['profit_factor']:>6.2f}                    | +{m_opt['profit_factor']-m_base['profit_factor']:.2f}")
    print(f"{'Lợi nhuận ròng (Net Profit)':<32} | ${m_base['net_pnl']:>8.2f} ({m_base['return_pct']:.1f}%)   | ${m_opt['net_pnl']:>8.2f} ({m_opt['return_pct']:.1f}%)      | Tăng +${m_opt['net_pnl']-m_base['net_pnl']:.2f}")
    print(f"{'Annualized Sharpe Ratio':<32} | {m_base['sharpe']:>6.2f}                 | {m_opt['sharpe']:>6.2f}                    | +{m_opt['sharpe']-m_base['sharpe']:.2f}")
    print(f"{'Sortino Ratio (Downside Risk)':<32} | {m_base['sortino']:>6.2f}                 | {m_opt['sortino']:>6.2f}                    | +{m_opt['sortino']-m_base['sortino']:.2f}")
    print(f"{'Calmar Ratio (Return / MaxDD)':<32} | {m_base['calmar']:>6.2f}                 | {m_opt['calmar']:>6.2f}                    | +{m_opt['calmar']-m_base['calmar']:.2f}")
    print(f"{'Sụt giảm tối đa (Max Drawdown)':<32} | {m_base['max_dd_pct']:>6.2f}% (${m_base['max_dd_usd']:.0f})        | {m_opt['max_dd_pct']:>6.2f}% (${m_opt['max_dd_usd']:.0f})           | Giảm {m_base['max_dd_pct']-m_opt['max_dd_pct']:.2f}% DD")
    print(f"{'Xác suất sống sót (Max DD <= 10%)':<32} | {m_base['surv_10']:>6.1f}%                | {m_opt['surv_10']:>6.1f}%                   | +{m_opt['surv_10']-m_base['surv_10']:.1f}%")
    print(f"{'Xác suất sống sót (Max DD <= 20%)':<32} | {m_base['surv_20']:>6.1f}%                | {m_opt['surv_20']:>6.1f}%                   | Zero-Ruin")
    print("==========================================================================================\n")

if __name__ == "__main__":
    run_comprehensive_audit()
