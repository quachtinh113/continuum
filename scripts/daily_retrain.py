"""
NowTrading V9 — Daily ML Retrain Pipeline
==========================================
Chạy mỗi ngày lúc 22:00 UTC (05:00 sáng VN) qua Windows Task Scheduler.

Logic:
1. Load logs/training_data.csv (tích lũy từ tất cả backtests + live trades)
2. Validate dữ liệu đủ mẫu (tối thiểu 50 trades)
3. Split train/test (80/20)
4. Retrain XGBoost mới
5. So sánh AUC mới vs AUC model hiện tại
6. Deploy nếu AUC mới >= AUC cũ - 0.02 (cho phép sai số nhỏ)
7. Ghi log kết quả vào logs/retrain_log.csv
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timezone

# Setup path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Suppress bot logging
import src.audit_logger
src.audit_logger.log_info = lambda *a, **k: None
src.audit_logger.log_error = lambda *a, **k: None

import pandas as pd
import numpy as np

try:
    import xgboost as xgb
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import roc_auc_score
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

# ── Paths ─────────────────────────────────────────────────────────────────────
TRAINING_DATA_PATH = PROJECT_ROOT / "logs" / "training_data.csv"
MODEL_PATH         = PROJECT_ROOT / "src" / "ml" / "gatekeeper_v1.json"
BACKUP_MODEL_PATH  = PROJECT_ROOT / "src" / "ml" / "gatekeeper_v1.json.bak"
RETRAIN_LOG_PATH   = PROJECT_ROOT / "logs" / "retrain_log.csv"

FEATURE_COLS = ["RSI_M15", "RSI_H1", "RSI_H4", "ADX", "ATR", "hour"]
EXTENDED_FEATURES = ["RSI_Delta", "Volatility_Index", "Session_Code", "RSI_H1_Div", "Trend_Vol_Ratio"] + FEATURE_COLS
MIN_SAMPLES = 50        # Không train nếu ít hơn 50 mẫu
AUC_TOLERANCE = 0.02    # Cho phép AUC mới thấp hơn tối đa 0.02


def load_training_data() -> pd.DataFrame:
    """Load và làm sạch dữ liệu training."""
    if not TRAINING_DATA_PATH.exists():
        raise FileNotFoundError(f"Training data not found: {TRAINING_DATA_PATH}")
    
    df = pd.read_csv(TRAINING_DATA_PATH)
    print(f"Loaded {len(df)} total rows from training_data.csv")
    
    # Drop rows thiếu feature
    df = df.dropna(subset=FEATURE_COLS + ["is_win"])
    print(f"After dropna: {len(df)} valid rows")
    
    # Recalculate features to ensure consistency and prevent dirty cache columns
    df["RSI_Delta"] = df["RSI_H4"] - df["RSI_M15"]
    
    def get_approx_price(symbol: str) -> float:
        symbol = symbol.replace("m", "").upper()
        if "JPY" in symbol:
            return 160.0
        if symbol in ["US30", "DJI"]:
            return 39000.0
        if symbol in ["US100", "NDX"]:
            return 19000.0
        if symbol in ["US500", "SPX"]:
            return 5200.0
        if symbol in ["XAUUSD", "GOLD"]:
            return 2330.0
        if symbol in ["BTCUSD", "BTC"]:
            return 65000.0
        return 1.1

    df["ATR"] = df["ATR"] / df["symbol"].apply(get_approx_price)
    df["Volatility_Index"] = df["ATR"]
        
    # New engineered features for quant risk enhancements
    session_map = {"ASIA": 0, "EUROPE": 1, "US": 2, "OVERLAP_ASIA_EU": 3, "OVERLAP_EU_US": 4, "OFF": -1}
    df["Session_Code"] = df["session"].map(session_map).fillna(-1)
    df["RSI_H1_Div"] = (df["RSI_H1"] - 50.0).abs()
    df["Trend_Vol_Ratio"] = df["ADX"] * df["ATR"]
    
    return df


def evaluate_current_model(df: pd.DataFrame) -> float:
    """Tính AUC của model hiện tại trên toàn bộ dataset."""
    if not MODEL_PATH.exists() or not HAS_XGB:
        return 0.0
    
    try:
        model = xgb.Booster()
        model.load_model(str(MODEL_PATH))
        
        X = df[EXTENDED_FEATURES]
        y = df["is_win"]
        
        dtest = xgb.DMatrix(X)
        preds = model.predict(dtest)
        # Model dự đoán LOSS_THREAT nên score thấp = win
        # Đảo chiều để tính AUC win rate
        auc = roc_auc_score(y, 1 - preds)
        return round(float(auc), 4)
    except Exception as e:
        print(f"Could not evaluate current model: {e}")
        return 0.0


def train_new_model(df: pd.DataFrame) -> tuple:
    """
    Train XGBoost mới và trả về (model, auc_train, auc_test).
    """
    X = df[EXTENDED_FEATURES]
    y = 1 - df["is_win"]   # Train to predict LOSS_THREAT
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    dtrain = xgb.DMatrix(X_train, label=y_train)
    dtest  = xgb.DMatrix(X_test,  label=y_test)
    
    params = {
        "max_depth": 4,
        "eta": 0.05,
        "objective": "binary:logistic",
        "eval_metric": "auc",
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 5,
        "seed": 42,
    }
    
    evals = [(dtrain, "train"), (dtest, "eval")]
    model = xgb.train(
        params, dtrain,
        num_boost_round=200,
        evals=evals,
        early_stopping_rounds=20,
        verbose_eval=False,
    )
    
    # Tính AUC trên test set và train set (đảo chiều so với LOSS_THREAT để lấy win rate AUC)
    preds_test = model.predict(dtest)
    auc_test = roc_auc_score(df.loc[y_test.index, "is_win"], 1 - preds_test)
    
    preds_train = model.predict(dtrain)
    auc_train = roc_auc_score(df.loc[y_train.index, "is_win"], 1 - preds_train)
    
    return model, round(float(auc_train), 4), round(float(auc_test), 4)


def save_retrain_log(
    timestamp: str,
    n_samples: int,
    auc_old: float,
    auc_new: float,
    deployed: bool,
    reason: str
):
    """Ghi kết quả retrain vào CSV log."""
    RETRAIN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    row = {
        "timestamp": timestamp,
        "n_samples": n_samples,
        "auc_old": auc_old,
        "auc_new_test": auc_new,
        "deployed": deployed,
        "reason": reason,
    }
    
    log_df = pd.DataFrame([row])
    if RETRAIN_LOG_PATH.exists():
        log_df.to_csv(RETRAIN_LOG_PATH, mode="a", header=False, index=False)
    else:
        log_df.to_csv(RETRAIN_LOG_PATH, index=False)


def main():
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print("=" * 60)
    print("  NowTrading V9 - Daily ML Retrain Pipeline")
    print(f"  {timestamp}")
    print("=" * 60)
    
    # 0. Run Nightly Audit to analyze logs and extract lessons
    try:
        from scripts.nightly_audit import main as run_audit
        run_audit()
    except Exception as e:
        print(f"Warning: Nightly Audit failed to run: {e}")
    print("-" * 60)
    
    if not HAS_XGB:
        print("ERROR: XGBoost not installed. Retrain skipped.")
        return
    
    # 1. Load data
    try:
        df = load_training_data()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return
    
    n_samples = len(df)
    if n_samples < MIN_SAMPLES:
        msg = f"Insufficient data: {n_samples} samples < {MIN_SAMPLES} minimum. Skipping."
        print(msg)
        save_retrain_log(timestamp, n_samples, 0.0, 0.0, False, msg)
        return
    
    # 2. Evaluate current model
    auc_old = evaluate_current_model(df)
    print(f"Current model AUC (on full dataset): {auc_old:.4f}")
    
    # 3. Train new model
    print(f"\nTraining new model on {n_samples} samples...")
    try:
        new_model, auc_train, auc_test = train_new_model(df)
    except Exception as e:
        msg = f"Training failed: {e}"
        print(f"ERROR: {msg}")
        save_retrain_log(timestamp, n_samples, auc_old, 0.0, False, msg)
        return
    
    print(f"New model - Train AUC: {auc_train:.4f} | Test AUC: {auc_test:.4f}")
    
    # 4. Deploy decision
    deploy_threshold = auc_old - AUC_TOLERANCE
    if auc_test >= deploy_threshold:
        # Backup model cũ trước
        if MODEL_PATH.exists():
            import shutil
            shutil.copy2(str(MODEL_PATH), str(BACKUP_MODEL_PATH))
            print(f"Backed up old model to: {BACKUP_MODEL_PATH}")
        
        # Save model mới
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        new_model.save_model(str(MODEL_PATH))
        
        improvement = auc_test - auc_old
        if improvement > 0:
            reason = f"Deployed: AUC improved by +{improvement:.4f} ({auc_old:.4f} -> {auc_test:.4f})"
        else:
            reason = f"Deployed: AUC within tolerance ({auc_old:.4f} -> {auc_test:.4f}, diff={improvement:.4f})"
        
        print(f"\n[DEPLOYED] {reason}")
        save_retrain_log(timestamp, n_samples, auc_old, auc_test, True, reason)
    else:
        reason = f"Rejected: New AUC {auc_test:.4f} < threshold {deploy_threshold:.4f} (old={auc_old:.4f} - tol={AUC_TOLERANCE})"
        print(f"\n[REJECTED] {reason}")
        print("Keeping old model.")
        save_retrain_log(timestamp, n_samples, auc_old, auc_test, False, reason)
    
    print("\nRetrain pipeline complete.")
    print(f"Log saved to: {RETRAIN_LOG_PATH}")


if __name__ == "__main__":
    main()
