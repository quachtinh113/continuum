import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone, timedelta
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
import xgboost as xgb

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ml.feature_engineering import build_institutional_features

def evaluate_existing_model(X_val: pd.DataFrame, y_val: pd.Series, model_path: str = "src/ml/gatekeeper_v1.json") -> float:
    """Evaluates current deployed XGBoost model on validation set."""
    if not os.path.exists(model_path) or len(np.unique(y_val)) < 2:
        return 0.50
    try:
        booster = xgb.Booster()
        booster.load_model(model_path)
        feature_names = getattr(booster, "feature_names", list(X_val.columns))
        
        # Align features
        X_eval = X_val.reindex(columns=feature_names, fill_value=0.0)
        dtest = xgb.DMatrix(X_eval, feature_names=feature_names)
        preds = booster.predict(dtest)
        auc = roc_auc_score(y_val, preds)
        return float(auc)
    except Exception:
        return 0.50

def run_weekly_rolling_retrain(data_path: str = 'logs/training_data.csv', window_days: int = 540):
    sys.stdout.reconfigure(encoding='utf-8')
    now_utc = datetime.now(timezone.utc)
    timestamp_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    retrain_csv = logs_dir / "retrain_log.csv"
    scheduler_log = logs_dir / "retrain_scheduler.log"

    def append_scheduler_log(msg: str):
        print(msg)
        with open(scheduler_log, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp_str}] {msg}\n")

    append_scheduler_log("===========================================================")
    append_scheduler_log("🔄 WEEKLY ROLLING ML RETRAINING PIPELINE (18-MONTH WINDOW)")
    append_scheduler_log("===========================================================")

    if not os.path.exists(data_path):
        append_scheduler_log(f"❌ Cannot find training data file at: {data_path}")
        return

    df_raw = pd.read_csv(data_path)
    if df_raw.empty:
        append_scheduler_log("❌ Training dataset is empty.")
        return

    # Filter rolling 18-month window (540 days)
    if 'entry_time' in df_raw.columns:
        df_raw['entry_dt'] = pd.to_datetime(df_raw['entry_time'], errors='coerce', utc=True)
        cutoff_date = now_utc - timedelta(days=window_days)
        df_window = df_raw[df_raw['entry_dt'] >= cutoff_date].copy()
    else:
        df_window = df_raw.copy()

    n_samples = len(df_window)
    append_scheduler_log(f"Filtered 18-Month Rolling Window ({window_days} days): {n_samples} trade samples (out of {len(df_raw)} total).")

    if n_samples < 30:
        msg = f"Rejected: Insufficient samples in 18-month window ({n_samples} < 30)."
        append_scheduler_log(f"⚠️ {msg}")
        _log_to_retrain_csv(retrain_csv, timestamp_str, n_samples, 0.0, 0.0, False, msg)
        return

    # Feature Engineering
    df_feat = build_institutional_features(df_window)

    feature_cols = [
        'er_ratio',
        'atr_ratio',
        'rsi_h1_delta',
        'rsi_m15_delta',
        'adx',
        'rsi_m15',
    ]
    feature_cols = [c for c in feature_cols if c in df_feat.columns]
    target_col = 'target_is_loss'

    if target_col not in df_feat.columns or len(feature_cols) == 0:
        msg = "Rejected: Missing target column or feature columns."
        append_scheduler_log(f"❌ {msg}")
        _log_to_retrain_csv(retrain_csv, timestamp_str, n_samples, 0.0, 0.0, False, msg)
        return

    X = df_feat[feature_cols]
    y = df_feat[target_col]

    if len(np.unique(y)) < 2:
        msg = f"Rejected: Single class label in target (y={np.unique(y)})."
        append_scheduler_log(f"⚠️ {msg}")
        _log_to_retrain_csv(retrain_csv, timestamp_str, n_samples, 0.0, 0.0, False, msg)
        return

    # Time-Series Split 5 Folds
    n_splits = min(5, n_samples // 10)
    if n_splits < 2:
        n_splits = 2

    tscv = TimeSeriesSplit(n_splits=n_splits)
    auc_scores = []
    old_auc_scores = []

    model_path = "src/ml/gatekeeper_v1.json"

    fold = 1
    for train_idx, val_idx in tscv.split(X):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

        if len(np.unique(y_val)) < 2 or len(np.unique(y_train)) < 2:
            fold += 1
            continue

        model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=3,
            learning_rate=0.03,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=1.0,
            reg_lambda=2.0,
            random_state=42,
            eval_metric='auc',
        )

        model.fit(X_train, y_train)
        preds_prob = model.predict_proba(X_val)[:, 1]
        auc = roc_auc_score(y_val, preds_prob)
        auc_scores.append(auc)

        old_auc = evaluate_existing_model(X_val, y_val, model_path)
        old_auc_scores.append(old_auc)

        append_scheduler_log(f"Fold {fold} | Train: {len(X_train)} | Val: {len(X_val)} | OOS AUC New: {auc:.4f} | Old AUC: {old_auc:.4f}")
        fold += 1

    auc_new = float(np.mean(auc_scores)) if auc_scores else 0.50
    auc_old = float(np.mean(old_auc_scores)) if old_auc_scores else 0.50

    append_scheduler_log("-" * 59)
    append_scheduler_log(f"🎯 OOS AUC New Model: {auc_new:.4f} │ Baseline AUC Old Model: {auc_old:.4f}")

    # Safety Gate Criteria: New AUC >= 0.55 AND New AUC >= Old AUC - 0.02
    min_required_auc = max(0.55, auc_old - 0.02)
    deployed = False

    if auc_new >= min_required_auc:
        deployed = True
        reason = f"Deployed: AUC {auc_new:.4f} >= threshold {min_required_auc:.4f} (Old AUC={auc_old:.4f})"
        append_scheduler_log(f"🟢 {reason}")

        # Retrain on full 18-month window and export
        final_model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=3,
            learning_rate=0.03,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=1.0,
            reg_lambda=2.0,
            random_state=42,
        )
        final_model.fit(X, y)
        os.makedirs("src/ml", exist_ok=True)
        final_model.save_model(model_path)
        append_scheduler_log(f"✅ Successfully exported updated model to: {model_path}")
    else:
        reason = f"Rejected: AUC {auc_new:.4f} < threshold {min_required_auc:.4f} (Old AUC={auc_old:.4f})"
        append_scheduler_log(f"🟡 {reason}")

    _log_to_retrain_csv(retrain_csv, timestamp_str, n_samples, auc_old, auc_new, deployed, reason)
    append_scheduler_log("===========================================================\n")

def _log_to_retrain_csv(csv_path: Path, timestamp: str, n_samples: int, auc_old: float, auc_new: float, deployed: bool, reason: str):
    row = {
        "timestamp": timestamp,
        "n_samples": n_samples,
        "auc_old": round(auc_old, 4),
        "auc_new_test": round(auc_new, 4),
        "deployed": deployed,
        "reason": reason
    }
    df_row = pd.DataFrame([row])
    if csv_path.exists():
        df_row.to_csv(csv_path, mode="a", header=False, index=False)
    else:
        df_row.to_csv(csv_path, mode="w", header=True, index=False)

if __name__ == "__main__":
    run_weekly_rolling_retrain()
