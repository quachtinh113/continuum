"""Read-only trace of the live pipeline: MT5 data -> indicators -> regime -> alpha signal -> governor.
Uses the bot's own components/methods; never routes orders. Safe to run beside the live bot."""
import sys, os, time, types
sys.stdout.reconfigure(encoding='utf-8'); sys.path.insert(0, os.path.abspath('.'))
import numpy as np, pandas as pd
from datetime import datetime, timezone
from config import settings
from src.mt5_connector import MT5Connector
from src.session_manager import get_current_session, is_weekend
from v9_continuum.main import V9ContinuumBot
from v9_continuum.layers.signal import SMCEngine, MLSignalEngine, Signal
from v9_continuum.layers.regime import EuropeRegimeDetector, KalmanFilterTracker, calculate_adx, calculate_rsi
from v9_continuum.core.governor import PortfolioGovernor
from src.ml.dca_gate import build_gate_features

TF_MIN = {"M15": 15, "H1": 60, "H4": 240}
now = datetime.now(timezone.utc)
session = get_current_session(now)
print(f"UTC now {now:%Y-%m-%d %H:%M:%S} | session={session.value} | weekend={is_weekend(now)}")
print(f"HYBRID flags: stop={settings.SOFT_ATR_MULTIPLIER} veto={settings.ML_ENTRY_VETO_ACTIVE} softML={settings.ML_SOFT_SL_ACTIVE} "
      f"12h={settings.ML_12H_DECISION_ACTIVE} sizing={settings.ML_SIZING_ACTIVE} maxDCA={settings.MAX_DCA_LAYERS} gate={settings.DCA_ML_GATE_ACTIVE}@{settings.DCA_ML_GATE_THRESHOLD} mask={settings.SESSION_MASK_ACTIVE}")

# ---- 1. DATA LAYER ----
t0 = time.time(); conn = MT5Connector(); ok = conn.connect()
print(f"\n[1] MT5 connect: {ok} ({(time.time()-t0)*1000:.0f} ms) | connected={conn.is_connected if not callable(conn.is_connected) else conn.is_connected()}")
acct = conn.get_account_info(); print(f"    account: {acct}")

shim = types.SimpleNamespace(connector=conn, smc_engine=SMCEngine(), europe_detector=EuropeRegimeDetector(),
                             kalman_trackers={}, ml_engine=MLSignalEngine(), governor=PortfolioGovernor())
gate = MLSignalEngine(settings.DCA_ML_GATE_MODEL)
print(f"    models: primary ready={shim.ml_engine.is_ready} | dca-gate ready={gate.is_ready} feats={len(gate.model.feature_names) if gate.is_ready else 0}")

symbols = ["AUDUSD", "NZDUSD", "USDJPY", "XAUUSD", "US30", "BTCUSD"]
tokens = []
print(f"\n[2] DATA QUALITY per symbol (bars, last closed bar age, NaN, gaps)")
for sym in symbols:
    row = {}
    for tf in ("M15", "H1", "H4"):
        t1 = time.time(); df = conn.get_rates(sym, tf, 100); dt = (time.time()-t1)*1000
        if df is None or df.empty:
            row[tf] = f"{tf}:NONE"; continue
        tcol = pd.to_datetime(df["time"], utc=True)
        closed = df.iloc[:-1]
        last_closed_age_min = (now - tcol.iloc[-2]).total_seconds()/60 - TF_MIN[tf]
        nan = int(df[["open","high","low","close"]].isna().sum().sum())
        diffs = tcol.diff().dt.total_seconds().div(60).iloc[1:]
        gaps = int((diffs > TF_MIN[tf]*1.5).sum())
        row[tf] = f"{tf}:{len(df)}b age={last_closed_age_min:.0f}m nan={nan} gaps={gaps} {dt:.0f}ms"
    print(f"  {sym:7s} " + " | ".join(row.values()))

print(f"\n[3] ALPHA BLOCK (evaluate_symbol_signal) + SESSION MASK + FEATURES")
blocked = settings.ENTRY_BLOCKED_HOURS if settings.SESSION_MASK_ACTIVE else {}
for sym in symbols:
    masked = sym in blocked and now.hour in blocked[sym]
    m15 = conn.get_rates(sym, "M15", 100); h1 = conn.get_rates(sym, "H1", 100); h4 = conn.get_rates(sym, "H4", 100)
    if m15 is None or h1 is None:
        print(f"  {sym:7s} NO DATA"); continue
    t1 = time.time()
    sig, reason, adx, spread = V9ContinuumBot.evaluate_symbol_signal(shim, sym, session, m15, h1)
    # Kalman scale diagnostic: z = residual / sqrt(p+r) with ABSOLUTE q,r -> depends on price units
    kf = KalmanFilterTracker(); cp = m15["close"].values
    for p_ in cp[:-1]: kf.update(p_)
    _, zk = kf.update(cp[-1]); last_move = abs(cp[-1]-cp[-2])
    print(f"  {sym:7s} kalman z={zk:+8.2f} | last M15 move={last_move:.5g} | sqrt(p+r)={np.sqrt(kf.p+kf.r):.4f} (price units) | rel move={last_move/cp[-1]*1e4:.1f} bp")
    dt = (time.time()-t1)*1000
    cm15, ch1, ch4 = m15.iloc[:-1], h1.iloc[:-1], (h4.iloc[:-1] if h4 is not None else None)
    feat = build_gate_features(sym, "BUY" if sig != Signal.SELL else "SELL", cm15, ch1, ch4, now, session)
    nan_feat = [k for k, v in feat.items() if v is None or (isinstance(v, float) and np.isnan(v))]
    print(f"  {sym:7s} mask={'BLOCKED' if masked else 'open':7s} sig={sig.value:4s} adx={adx:5.1f} spread={spread:.1f} "
          f"rsi15={feat['rsi_m15']:.1f} rsiH1={feat['RSI_H1']:.1f} rsiH4={feat['RSI_H4']:.1f} atr={feat['ATR']:.5g} er={feat['er_ratio']:.2f} "
          f"{dt:.0f}ms {'NaN:'+str(nan_feat) if nan_feat else ''}\n           reason: {reason}")
    if sig != Signal.HOLD and not masked:
        tokens.append({"symbol": sym, "direction": sig.value, "adx": adx, "spread": spread, "atr": feat["ATR"],
                       "reason": reason, "price": float(cm15["close"].iloc[-1]), "loss_prob": None, "features": feat})

print(f"\n[4] GOVERNOR token queue: {len(tokens)} candidate(s) -> ", end="")
winner = shim.governor.process_token_queue(tokens) if tokens else None
print(f"winner={winner['symbol'] + ' ' + winner['direction'] if winner else None}")
if winner:
    approved, why = shim.governor.evaluate_risk_matrix(winner["symbol"], [], acct["equity"] if acct else 0.0, acct["balance"] if acct else 0.0, now.timestamp())
    print(f"    risk matrix: approved={approved} ({why})")
conn.disconnect(); print("\n[done] no orders were sent.")
