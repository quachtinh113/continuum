"""V9 Continuum - 36-Month Institutional Backtest Runner.

Runs the engine over 36 months of real MT5 M15/H1/H4 data and emits
a full metric set plus a per-trade CSV used downstream for ML training.
"""
import os
import sys
import json
import time
import math
import argparse
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from v9_continuum.backtest import V9ContinuumBacktester

ELITE_6 = ["AUDUSD", "NZDUSD", "USDJPY", "XAUUSD", "US30", "BTCUSD"]
FULL_12 = ELITE_6 + ["EURUSD", "GBPUSD", "USDCAD", "USDCHF", "US500", "US100"]


def trade_frame(portfolio) -> pd.DataFrame:
    rows = []
    for c in portfolio.closed_cycles:
        row = {
            "symbol": c["symbol"],
            "direction": c["direction"],
            "entry_time": c["entry_time"],
            "exit_time": c["exit_time"],
            "entry_price": c["entry_price"],
            "exit_price": c["exit_price"],
            "pnl": c["final_pnl"],
            "holding_hours": c["holding_hours"],
            "dca_layers": c["num_dca_layers"],
            "reason": c["close_reason"],
            "session": c.get("session", ""),
        }
        for k, v in (c.get("features") or {}).items():
            row["f_" + str(k)] = v
        rows.append(row)
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("exit_time").reset_index(drop=True)
    return df


def risk_metrics(df: pd.DataFrame, initial_balance: float, years: float) -> dict:
    """Daily-resampled risk metrics computed off the realised equity curve."""
    if df.empty:
        return {}
    eq = initial_balance + df["pnl"].cumsum()
    peak = eq.cummax()
    dd = peak - eq
    max_dd_usd = float(dd.max())
    max_dd_pct = float((dd / peak).max() * 100.0)

    daily = df.set_index(pd.to_datetime(df["exit_time"], utc=True))["pnl"].resample("D").sum()
    daily = daily[daily.index.dayofweek < 5]
    bal = initial_balance
    rets = []
    for x in daily.values:
        rets.append(x / bal if bal > 0 else 0.0)
        bal += x
    rets = np.array(rets)
    mu = rets.mean()
    sd = rets.std(ddof=1)
    sharpe = float(mu / sd * math.sqrt(252)) if sd > 0 else 0.0
    downs = rets[rets < 0]
    dsd = downs.std(ddof=1) if len(downs) > 1 else 0.0
    sortino = float(mu / dsd * math.sqrt(252)) if dsd > 0 else 0.0

    net = float(df["pnl"].sum())
    ann_ret_pct = (net / initial_balance * 100.0) / years
    calmar = ann_ret_pct / max_dd_pct if max_dd_pct > 0 else 0.0
    recovery = net / max_dd_usd if max_dd_usd > 0 else 0.0

    streak = 0
    worst = 0
    for x in df["pnl"].values:
        streak = streak + 1 if x <= 0 else 0
        worst = max(worst, streak)

    return {
        "max_dd_usd": max_dd_usd,
        "max_dd_pct": max_dd_pct,
        "sharpe": sharpe,
        "sortino": sortino,
        "annual_return_pct": ann_ret_pct,
        "calmar": calmar,
        "recovery_factor": recovery,
        "max_loss_streak": worst,
        "trading_days": int(len(daily)),
        "win_days": int((daily > 0).sum()),
        "loss_days": int((daily < 0).sum()),
    }


def summarize(tag: str, df: pd.DataFrame, metrics: dict, extra: dict) -> str:
    bar = "=" * 78
    L = ["", bar, " " + tag, bar]
    if df.empty:
        L.append(" NO TRADES")
        return "\n".join(L)

    n_win = int((df.pnl > 0).sum())
    n_loss = int((df.pnl <= 0).sum())
    L.append(" Trades {} | Win {} | Loss {} | WR {:.2f}%".format(
        len(df), n_win, n_loss, metrics["win_rate"]))
    L.append(" Net PnL ${:+,.2f} ({:+.2f}%) | Annualised {:+.2f}%/yr".format(
        metrics["total_profit_usd"], metrics["profit_percent"], extra["annual_return_pct"]))
    L.append(" Profit Factor {} | Expectancy ${:+.2f}/trade".format(
        metrics["profit_factor"], df.pnl.mean()))
    L.append(" Max DD ${:,.2f} ({:.2f}%) | Max loss streak {}".format(
        extra["max_dd_usd"], extra["max_dd_pct"], extra["max_loss_streak"]))
    L.append(" Sharpe {:.2f} | Sortino {:.2f} | Calmar {:.2f} | Recovery {:.2f} | PSR {:.1f}%".format(
        extra["sharpe"], extra["sortino"], extra["calmar"], extra["recovery_factor"],
        metrics["psr"] * 100))
    L.append(" Trading days {} ({}W/{}L) | Avg hold {:.1f}h | Avg DCA {:.2f}".format(
        extra["trading_days"], extra["win_days"], extra["loss_days"],
        metrics["avg_holding_hours"], metrics["avg_dca_layers"]))

    L.append("")
    L.append(" Per symbol:")
    L.append("  {:9s} {:>5s} {:>7s} {:>11s} {:>6s} {:>9s}".format(
        "SYMBOL", "N", "WR%", "NET$", "PF", "EXPECT$"))
    for s, g in df.groupby("symbol"):
        gp = g.loc[g.pnl > 0, "pnl"].sum()
        gl = abs(g.loc[g.pnl <= 0, "pnl"].sum())
        pf = gp / gl if gl > 0 else float("inf")
        L.append("  {:9s} {:5d} {:6.1f}% {:11,.2f} {:6.2f} {:9.2f}".format(
            s, len(g), (g.pnl > 0).mean() * 100, g.pnl.sum(), pf, g.pnl.mean()))

    L.append("")
    L.append(" Per year:")
    yr = df.copy()
    yr["y"] = pd.to_datetime(yr["exit_time"], utc=True).dt.year
    for y, g in yr.groupby("y"):
        gp = g.loc[g.pnl > 0, "pnl"].sum()
        gl = abs(g.loc[g.pnl <= 0, "pnl"].sum())
        pf = gp / gl if gl > 0 else float("inf")
        L.append("  {}  n={:5d}  WR {:5.1f}%  Net ${:+10,.2f}  PF {:.2f}".format(
            y, len(g), (g.pnl > 0).mean() * 100, g.pnl.sum(), pf))

    L.append("")
    L.append(" Close reasons:")
    for r, n in sorted(metrics["reasons"].items(), key=lambda kv: -kv[1]):
        sub = df[df.reason == r]
        L.append("  {:22s} n={:5d}  Net ${:+10,.2f}  WR {:5.1f}%  Avg ${:+7.2f}".format(
            r, n, sub.pnl.sum(), (sub.pnl > 0).mean() * 100, sub.pnl.mean()))
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", default="elite6", choices=["elite6", "full12"])
    ap.add_argument("--veto", type=float, default=0.85)
    ap.add_argument("--balance", type=float, default=10000.0)
    ap.add_argument("--tag", default=None)
    ap.add_argument("--model", default=None, help="Override ML gatekeeper model path")
    ap.add_argument("--dca-veto", type=float, default=None,
                    help="ML DCA gate threshold (skip DCA when loss prob above this)")
    ap.add_argument("--start", default="2023-08-21")
    ap.add_argument("--end", default="2026-08-21")
    ap.add_argument("--symbols", default=None, help="Comma-separated symbol override")
    ap.add_argument("--no-dca", action="store_true", help="Disable DCA layers entirely")
    ap.add_argument("--soft-atr", type=float, default=None, help="Override SOFT_ATR stop multiplier")
    ap.add_argument("--max-dca", type=int, default=2, help="Max passive DCA layers (0-2)")
    ap.add_argument("--no-ml", action="store_true", help="Pure-indicator mode: no ML veto / 12h decision / sizing")
    ap.add_argument("--real-spread", action="store_true", help="Use recorded per-bar spread for costs and gate")
    ap.add_argument("--spread-gate", type=float, default=None, help="Skip entries when spread > K x rolling median")
    ap.add_argument("--kalman", default="fixed", choices=["fixed", "adaptive", "adaptive_fx"], help="Asia Kalman z-score mode")
    ap.add_argument("--dca-model", default=None, help="Dedicated ML model for the DCA gate")
    ap.add_argument("--session-mask", action="store_true",
                    help="Block stable-negative symbol-session combos (AUDUSD US; NZDUSD EU+US; US30 EU-US overlap)")
    args = ap.parse_args()

    symbols = ELITE_6 if args.universe == "elite6" else FULL_12
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    start = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    years = (end - start).days / 365.25

    tag = args.tag or "{}_veto{}".format(args.universe, args.veto)
    print("V9 CONTINUUM :: 36-MONTH BACKTEST :: {}".format(tag))
    print("Universe: {}".format(symbols))
    print("Window  : {:%Y-%m-%d} -> {:%Y-%m-%d} ({:.2f} years)".format(start, end, years))
    print("ML veto threshold: {} | Initial balance ${:,.0f}".format(args.veto, args.balance))
    print("")

    t0 = time.time()
    bt = V9ContinuumBacktester(data_dir="data/historical_36m", ml_veto_threshold=args.veto,
                               ml_model_path=args.model, ml_dca_veto_threshold=args.dca_veto,
                               dca_multiplier_scale=(1e6 if args.no_dca else 1.0),
                               soft_atr_multiplier=args.soft_atr,
                               max_dca_layers=args.max_dca, ml_dca_model_path=args.dca_model,
                               ml_enabled=(not args.no_ml),
                               use_real_spread=args.real_spread, spread_gate_k=args.spread_gate,
                               kalman_mode=args.kalman,
                               entry_blocked_hours=({
                                   "AUDUSD": [16, 17, 18, 19, 20, 21],
                                   "NZDUSD": [9, 10, 11, 12, 16, 17, 18, 19, 20, 21],
                                   "US30": [13, 14, 15],
                               } if args.session_mask else None))
    portfolio, metrics = bt.run(symbols, start, end, initial_balance=args.balance)
    print("Simulation finished in {:.0f}s".format(time.time() - t0))

    df = trade_frame(portfolio)
    extra = risk_metrics(df, args.balance, years)

    out_dir = Path("reports/backtest_36m")
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "trades_{}.csv".format(tag), index=False)
    with open(out_dir / "metrics_{}.json".format(tag), "w", encoding="utf-8") as f:
        json.dump({"metrics": metrics, "risk": extra, "symbols": symbols,
                   "veto": args.veto, "years": years}, f, indent=2, default=str)

    txt = summarize("{} :: 36M :: ML veto {}".format(args.universe.upper(), args.veto),
                    df, metrics, extra)
    print(txt)
    (out_dir / "summary_{}.txt".format(tag)).write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
