"""V9 Continuum - daily PnL & health check (source of truth = MT5 deal history).

Writes reports/daily/YYYY-MM-DD.md and prints the same text. Exit code 2 when the
deployment drawdown limit is breached (so a scheduler / watchdog can alert).

Usage:  python scripts/daily_pnl_check.py [--deploy-start 2026-08-22] [--dd-limit 6.0]
"""
import os
import sys
import json
import glob
import argparse
import collections
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import MetaTrader5 as mt5

ELITE = ["AUDUSD", "NZDUSD", "USDJPY", "XAUUSD", "US30", "BTCUSD"]
PEAK_FILE = Path("logs/deploy_equity_peak.json")


def net(d):
    return d.profit + d.commission + d.swap


def stats(deals):
    p = [net(d) for d in deals]
    w = [x for x in p if x > 0]
    l = [x for x in p if x <= 0]
    gp, gl = sum(w), abs(sum(l))
    return {
        "n": len(p), "win": len(w), "loss": len(l),
        "wr": (len(w) / len(p) * 100) if p else 0.0,
        "net": sum(p), "pf": (gp / gl) if gl > 0 else (float("inf") if gp > 0 else 0.0),
        "avg": (sum(p) / len(p)) if p else 0.0,
        "best": max(p) if p else 0.0, "worst": min(p) if p else 0.0,
    }


def audit_counts(day_utc: str):
    """ROUTE / gate / DCA events per symbol from the bot's audit log for one UTC day."""
    c = collections.defaultdict(collections.Counter)
    for f in glob.glob(f"logs/audit_{day_utc}.jsonl"):
        for line in open(f, encoding="utf-8", errors="replace"):
            try:
                d = json.loads(line)
            except Exception:
                continue
            s = d.get("symbol")
            if not s:
                continue
            if d.get("execution_action"):
                c[s][d["execution_action"]] += 1
            if d.get("event") in ("CYCLE_OPEN", "CYCLE_CLOSE", "DCA_OPEN", "DCA_GATE_VETO"):
                c[s][d["event"]] += 1
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy-start", default="2026-08-22", help="UTC date the current live config went live")
    ap.add_argument("--dd-limit", type=float, default=6.0, help="Deployment drawdown limit %% (from equity peak)")
    args = ap.parse_args()

    if not mt5.initialize():
        print("MT5 init failed:", mt5.last_error()); sys.exit(1)
    acc = mt5.account_info()
    now = datetime.now(timezone.utc)
    today0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week0 = today0 - timedelta(days=today0.weekday())
    deploy0 = datetime.strptime(args.deploy_start, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    def closed(since):
        ds = mt5.history_deals_get(since, now + timedelta(hours=1)) or []
        return [d for d in ds if d.entry in (1, 3) and d.type in (0, 1)]

    d_today, d_week, d_deploy = closed(today0), closed(week0), closed(deploy0)
    s_today, s_week, s_deploy = stats(d_today), stats(d_week), stats(d_deploy)

    # ---- deployment drawdown from equity peak (persisted) ----
    peak = {"peak_equity": acc.equity, "peak_time": now.isoformat(), "deploy_start": args.deploy_start}
    if PEAK_FILE.exists():
        try:
            old = json.loads(PEAK_FILE.read_text(encoding="utf-8"))
            if old.get("deploy_start") == args.deploy_start and old.get("peak_equity", 0) > acc.equity:
                peak = old
        except Exception:
            pass
    PEAK_FILE.parent.mkdir(parents=True, exist_ok=True)
    PEAK_FILE.write_text(json.dumps(peak, indent=2), encoding="utf-8")
    dd_pct = (peak["peak_equity"] - acc.equity) / peak["peak_equity"] * 100 if peak["peak_equity"] > 0 else 0.0
    breached = dd_pct >= args.dd_limit

    # ---- bot health ----
    try:
        hb_age = int(now.timestamp() - int(open("logs/heartbeat.txt").read().strip()))
    except Exception:
        hb_age = -1
    try:
        pid = open("logs/bot.pid").read().strip()
    except Exception:
        pid = "?"
    lock_file = Path("logs/DEPLOY_DD_LOCK")
    open_pos = mt5.positions_get() or []

    # ---- audit per symbol (today, UTC) ----
    ac = audit_counts(today0.strftime("%Y-%m-%d"))

    L = []
    L.append(f"# V9 Continuum — Daily check {now:%Y-%m-%d %H:%M} UTC")
    L.append("")
    L.append(f"**Account** {acc.login} | balance ${acc.balance:,.2f} | equity ${acc.equity:,.2f} | open positions {len(open_pos)}")
    L.append(f"**Bot** pid {pid} | heartbeat age {hb_age}s {'✅' if 0 <= hb_age < 120 else '🚨 STALE/DEAD'} | DD lock file {'🔒 PRESENT' if lock_file.exists() else 'absent'}")
    L.append("")
    L.append(f"**Deployment DD** from peak ${peak['peak_equity']:,.2f} ({peak['peak_time'][:16]}): **{dd_pct:.2f}%** / limit {args.dd_limit:.1f}% → {'🚨 BREACHED — STOP NEW ENTRIES' if breached else '✅ ok'}")
    L.append("")
    L.append("| Window | Trades | W/L | WR | Net | PF | Avg | Best | Worst |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for name, s in (("Today", s_today), ("This week", s_week), (f"Since deploy {args.deploy_start}", s_deploy)):
        L.append(f"| {name} | {s['n']} | {s['win']}/{s['loss']} | {s['wr']:.0f}% | ${s['net']:+,.2f} | {s['pf']:.2f} | ${s['avg']:+.2f} | ${s['best']:+.2f} | ${s['worst']:+.2f} |")
    L.append("")
    L.append("**Per symbol since deploy (MT5):**")
    by = collections.defaultdict(list)
    for d in d_deploy:
        by[d.symbol].append(d)
    for sym in sorted(by):
        s = stats(by[sym])
        L.append(f"- {sym}: n={s['n']} WR {s['wr']:.0f}% net ${s['net']:+,.2f} PF {s['pf']:.2f}")
    if not by:
        L.append("- (no closed deals yet)")
    L.append("")
    L.append("**Bot decisions today (audit):** ROUTE = signal approved; check BTCUSD/US30 are no longer starved")
    for sym in ELITE:
        c = ac.get(sym, {})
        L.append(f"- {sym}: ROUTE {c.get('ROUTE', 0)} | BLOCKED {c.get('BLOCKED', 0)} | SPREAD_GATE {c.get('SPREAD_GATE', 0)} | CYCLE_OPEN {c.get('CYCLE_OPEN', 0)} | CYCLE_CLOSE {c.get('CYCLE_CLOSE', 0)} | DCA_OPEN {c.get('DCA_OPEN', 0)} | DCA_GATE_VETO {c.get('DCA_GATE_VETO', 0)}")
    mt5.shutdown()

    text = "\n".join(L)
    out = Path("reports/daily") / f"{now:%Y-%m-%d}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"\n[saved] {out}")
    sys.exit(2 if breached else 0)


if __name__ == "__main__":
    main()
