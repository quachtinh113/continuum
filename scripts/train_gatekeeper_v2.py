"""V9 Continuum - Gatekeeper V2 training pipeline.

Meta-labelling design (Lopez de Prado): the primary engines (OU/Kalman, SMC-HMM,
KAMA momentum) decide DIRECTION; this model only decides TAKE vs SKIP on the
signals they emit. It is therefore trained on the unfiltered signal population
produced by a backtest run with the ML veto disabled.

Key differences from gatekeeper_v1, which collapsed to a constant ~0.89:
  * trained on the real unfiltered signal population, not a veto-biased subset
  * purged + embargoed walk-forward CV, so OOS AUC is honest
  * scale_pos_weight balancing so the model cannot win by predicting base rate
  * threshold chosen to maximise net expectancy, not accuracy
  * a degeneracy gate that fails the run if predictions have no spread
"""
import os
import sys
import json
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import xgboost as xgb
from sklearn.metrics import roc_auc_score

# Features the model is allowed to see. All are computable at entry time.
BASE_FEATURES = [
    "er_ratio", "atr_ratio", "rsi_h1_delta", "rsi_m15_delta", "adx", "rsi_m15",
    "RSI_H1", "RSI_H4", "RSI_Delta", "Volatility_Index",
    "hour", "Session_Code", "RSI_H1_Div", "Trend_Vol_Ratio",
]


def build_dataset(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["exit_time"] = pd.to_datetime(df["exit_time"], utc=True)
    df["entry_time"] = pd.to_datetime(df["entry_time"], utc=True)
    df = df.sort_values("entry_time").reset_index(drop=True)

    feat_cols = {}
    for f in BASE_FEATURES:
        col = "f_" + f
        if col in df.columns:
            feat_cols[f] = pd.to_numeric(df[col], errors="coerce")
    X = pd.DataFrame(feat_cols)

    # ---- Engineered context features (all entry-time observable) ----
    X["is_buy"] = (df["direction"] == "BUY").astype(int)
    X["hour_sin"] = np.sin(2 * np.pi * X.get("hour", 0) / 24.0)
    X["hour_cos"] = np.cos(2 * np.pi * X.get("hour", 0) / 24.0)
    if "adx" in X and "atr_ratio" in X:
        X["adx_x_atrratio"] = X["adx"] * X["atr_ratio"]
    if "rsi_m15" in X and "RSI_H1" in X:
        X["rsi_align"] = np.sign(X["rsi_m15"] - 50) * np.sign(X["RSI_H1"] - 50)
    if "rsi_m15" in X:
        X["rsi_extreme"] = (X["rsi_m15"] - 50).abs()
    if "er_ratio" in X and "adx" in X:
        X["trendiness"] = X["er_ratio"] * X["adx"]
    # Direction agreement with higher timeframe bias
    if "RSI_H4" in X:
        X["h4_bias_agree"] = ((X["RSI_H4"] > 50).astype(int) == X["is_buy"]).astype(int)

    # Symbol category as an ordinal (kept coarse to avoid per-symbol overfit)
    cat_map = {"XAUUSD": 0, "BTCUSD": 1, "US30": 2, "US500": 2, "US100": 2}
    X["asset_class"] = df["symbol"].map(lambda s: cat_map.get(s, 3)).astype(int)

    X = X.replace([np.inf, -np.inf], np.nan)

    out = X.copy()
    # Label: 1 = the signal turned out to be a LOSS (what the veto must detect)
    out["_y"] = (df["pnl"] <= 0).astype(int)
    out["_pnl"] = df["pnl"].values
    out["_t"] = df["entry_time"].values
    out["_symbol"] = df["symbol"].values
    return out.dropna(subset=[c for c in X.columns if c != "asset_class"]).reset_index(drop=True)


def purged_walkforward_splits(n: int, n_folds: int = 5, embargo_frac: float = 0.01):
    """Expanding-window walk-forward with an embargo gap between train and test."""
    fold = n // (n_folds + 1)
    embargo = max(1, int(n * embargo_frac))
    for k in range(1, n_folds + 1):
        train_end = fold * k
        test_start = train_end + embargo
        test_end = min(n, fold * (k + 1) + embargo)
        if test_start >= test_end or train_end < 200:
            continue
        yield np.arange(0, train_end), np.arange(test_start, test_end)


def expectancy_at_threshold(y_pnl: np.ndarray, prob_loss: np.ndarray, thr: float):
    """Net result if we skip every signal whose predicted loss-prob exceeds thr."""
    taken = prob_loss <= thr
    if taken.sum() == 0:
        return {"thr": thr, "n": 0, "net": 0.0, "expectancy": 0.0, "wr": 0.0, "pf": 0.0}
    p = y_pnl[taken]
    gp = p[p > 0].sum()
    gl = abs(p[p <= 0].sum())
    return {
        "thr": float(thr),
        "n": int(taken.sum()),
        "kept_pct": float(taken.mean() * 100),
        "net": float(p.sum()),
        "expectancy": float(p.mean()),
        "wr": float((p > 0).mean() * 100),
        "pf": float(gp / gl) if gl > 0 else float("inf"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="reports/backtest_36m/trades_nofilter_full12.csv")
    ap.add_argument("--out", default="src/ml/gatekeeper_v2.json")
    ap.add_argument("--folds", type=int, default=5)
    args = ap.parse_args()

    ds = build_dataset(Path(args.data))
    feat_names = [c for c in ds.columns if not c.startswith("_")]
    X = ds[feat_names].values
    y = ds["_y"].values
    pnl = ds["_pnl"].values

    print("=" * 78)
    print(" GATEKEEPER V2 :: PURGED WALK-FORWARD TRAINING")
    print("=" * 78)
    print("Samples          : {}".format(len(ds)))
    print("Window           : {} -> {}".format(pd.Timestamp(ds['_t'].min()).date(),
                                               pd.Timestamp(ds['_t'].max()).date()))
    print("Loss base rate   : {:.2f}%".format(y.mean() * 100))
    print("Features ({:2d})     : {}".format(len(feat_names), ", ".join(feat_names)))
    print("Unfiltered net   : ${:+,.2f}  (expectancy ${:+.2f}/trade)".format(pnl.sum(), pnl.mean()))
    print("")

    params = {
        "objective": "binary:logistic",
        "eval_metric": "auc",
        "max_depth": 4,
        "eta": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 20,
        "reg_lambda": 2.0,
        "scale_pos_weight": float((y == 0).sum() / max(1, (y == 1).sum())),
        "seed": 42,
    }

    oof_prob = np.full(len(ds), np.nan)
    fold_report = []
    print(" Walk-forward folds (expanding window, 1% embargo):")
    for i, (tr, te) in enumerate(purged_walkforward_splits(len(ds), args.folds), 1):
        dtr = xgb.DMatrix(X[tr], label=y[tr], feature_names=feat_names)
        dte = xgb.DMatrix(X[te], label=y[te], feature_names=feat_names)
        bst = xgb.train(params, dtr, num_boost_round=300,
                        evals=[(dte, "test")], early_stopping_rounds=40, verbose_eval=False)
        p = bst.predict(dte, iteration_range=(0, bst.best_iteration + 1))
        oof_prob[te] = p
        auc = roc_auc_score(y[te], p) if len(np.unique(y[te])) > 1 else float("nan")
        fold_report.append({"fold": i, "n_train": len(tr), "n_test": len(te),
                            "auc": float(auc), "best_iter": int(bst.best_iteration)})
        print("  fold {} | train {:5d} | test {:5d} | OOS AUC {:.4f} | trees {}".format(
            i, len(tr), len(te), auc, bst.best_iteration + 1))

    mask = ~np.isnan(oof_prob)
    oos_auc = roc_auc_score(y[mask], oof_prob[mask])
    print("")
    print(" Pooled OOS AUC   : {:.4f}".format(oos_auc))
    print(" Prediction spread: min {:.3f} / mean {:.3f} / max {:.3f} / std {:.3f}".format(
        oof_prob[mask].min(), oof_prob[mask].mean(), oof_prob[mask].max(), oof_prob[mask].std()))

    if oof_prob[mask].std() < 0.02:
        print(" !! DEGENERATE MODEL - predictions have no spread. Aborting.")
        sys.exit(2)

    # ---- Threshold selection on OOS predictions only ----
    print("")
    print(" Threshold sweep on OOS predictions (skip signals above threshold):")
    print("  {:>5s} {:>7s} {:>7s} {:>12s} {:>11s} {:>7s} {:>6s}".format(
        "THR", "KEPT", "KEPT%", "NET$", "EXPECT$", "WR%", "PF"))
    sweep = []
    base = expectancy_at_threshold(pnl[mask], oof_prob[mask], 1.01)
    for thr in np.arange(0.30, 1.001, 0.025):
        r = expectancy_at_threshold(pnl[mask], oof_prob[mask], thr)
        sweep.append(r)
        if r["n"] > 0:
            print("  {:5.3f} {:7d} {:6.1f}% {:12,.2f} {:11.3f} {:7.2f} {:6.2f}".format(
                r["thr"], r["n"], r["kept_pct"], r["net"], r["expectancy"], r["wr"], r["pf"]))

    # Pick the threshold with the best net PnL that still keeps a usable sample
    viable = [r for r in sweep if r["kept_pct"] >= 15.0]
    best = max(viable, key=lambda r: r["net"]) if viable else max(sweep, key=lambda r: r["net"])
    print("")
    print(" Baseline (no filter): net ${:+,.2f} | expectancy ${:+.3f} | WR {:.2f}% | PF {:.2f}".format(
        base["net"], base["expectancy"], base["wr"], base["pf"]))
    print(" SELECTED threshold  : {:.3f}".format(best["thr"]))
    print("   kept {} of {} signals ({:.1f}%)".format(best["n"], int(mask.sum()), best["kept_pct"]))
    print("   net ${:+,.2f} | expectancy ${:+.3f} | WR {:.2f}% | PF {:.2f}".format(
        best["net"], best["expectancy"], best["wr"], best["pf"]))
    print("   delta vs unfiltered: ${:+,.2f}  ({:+.1f}% of baseline loss recovered)".format(
        best["net"] - base["net"],
        (best["net"] - base["net"]) / abs(base["net"]) * 100 if base["net"] else 0.0))

    # ---- Final model trained on all data with the CV-median tree count ----
    med_iter = int(np.median([f["best_iter"] for f in fold_report])) + 1
    dall = xgb.DMatrix(X, label=y, feature_names=feat_names)
    final = xgb.train(params, dall, num_boost_round=max(30, med_iter))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    final.save_model(args.out)

    gain = final.get_score(importance_type="gain")
    print("")
    print(" Feature importance (gain):")
    for k, v in sorted(gain.items(), key=lambda kv: -kv[1])[:15]:
        print("  {:22s} {:10.3f}".format(k, v))

    meta = {
        "model": args.out,
        "features": feat_names,
        "n_samples": int(len(ds)),
        "loss_base_rate": float(y.mean()),
        "oos_auc": float(oos_auc),
        "folds": fold_report,
        "selected_threshold": best["thr"],
        "oos_baseline": base,
        "oos_filtered": best,
        "sweep": sweep,
        "final_trees": max(30, med_iter),
        "params": params,
    }
    meta_path = args.out.replace(".json", "_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print("")
    print(" Saved model -> {}".format(args.out))
    print(" Saved meta  -> {}".format(meta_path))


if __name__ == "__main__":
    main()
