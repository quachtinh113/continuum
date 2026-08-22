"""Gold US-session improvement experiments over the full 36-month window.

Variants (XAUUSD-only runs, identical data/costs, one change at a time):
  A  baseline           - engine as-is, ML veto 0.85 (live threshold)
  B  +h4align           - US momentum entries must agree with H4 RSI bias
  C  +blockhours        - no new entries at 13, 20, 21 UTC (weak-hour cut)
  D  +h4align+block     - B and C combined
"""
import os
import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from v9_continuum.backtest import V9ContinuumBacktester

START = datetime(2023, 8, 21, tzinfo=timezone.utc)
END = datetime(2026, 8, 21, tzinfo=timezone.utc)
BAL = 10000.0

VARIANTS = {
    "A_baseline": {},
    "B_h4align": {"us_h4_align": ["XAUUSD"]},
    "C_blockhours": {"entry_blocked_hours": {"XAUUSD": [13, 20, 21]}},
    "D_combined": {"us_h4_align": ["XAUUSD"],
                   "entry_blocked_hours": {"XAUUSD": [13, 20, 21]}},
}


def run_variant(name, kw):
    t0 = time.time()
    bt = V9ContinuumBacktester(data_dir="data/historical_36m", ml_veto_threshold=0.85, **kw)
    p, m = bt.run(["XAUUSD"], START, END, initial_balance=BAL)
    rows = []
    for c in p.closed_cycles:
        rows.append({"pnl": c["final_pnl"], "reason": c["close_reason"],
                     "session": c.get("session", ""), "dir": c["direction"],
                     "entry_time": c["entry_time"], "dca": c["num_dca_layers"]})
    df = pd.DataFrame(rows)
    us = df[df.session.isin(["US", "OVERLAP_EU_US"])] if not df.empty else df
    out = {
        "name": name,
        "n": len(df),
        "net": float(df.pnl.sum()) if len(df) else 0.0,
        "wr": float((df.pnl > 0).mean() * 100) if len(df) else 0.0,
        "pf": m["profit_factor"],
        "dd_pct": m["max_drawdown_percent"],
        "us_n": len(us),
        "us_net": float(us.pnl.sum()) if len(us) else 0.0,
        "us_wr": float((us.pnl > 0).mean() * 100) if len(us) else 0.0,
        "elapsed": round(time.time() - t0),
    }
    df.to_csv("reports/backtest_36m/gold_{}.csv".format(name), index=False)
    print("  {:14s} n={:4d} net=${:+9.2f} WR={:5.1f}% PF={:<5} DD={:5.2f}% "
          "|| US-window n={:4d} net=${:+9.2f} WR={:5.1f}%  [{}s]".format(
              name, out["n"], out["net"], out["wr"], out["pf"], out["dd_pct"],
              out["us_n"], out["us_net"], out["us_wr"], out["elapsed"]))
    return out


def main():
    print("GOLD US-SESSION EXPERIMENTS :: XAUUSD only :: 36 months :: veto 0.85")
    results = []
    for name, kw in VARIANTS.items():
        results.append(run_variant(name, kw))
    Path("reports/backtest_36m").mkdir(parents=True, exist_ok=True)
    with open("reports/backtest_36m/gold_us_experiments.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
