import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
import xgboost as xgb

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ml.feature_engineering import build_institutional_features

def run_walk_forward_training(data_path: str = 'logs/training_data.csv'):
    sys.stdout.reconfigure(encoding='utf-8')
    if not os.path.exists(data_path):
        print(f'❌ Không tìm thấy file tập dữ liệu huấn luyện tại: {data_path}')
        return

    df = pd.read_csv(data_path)
    if len(df) < 30:
        print(f'⚠️ Số mẫu dữ liệu quá ít ({len(df)} mẫu). Cần tối thiểu 30 mẫu để huấn luyện Walk-Forward.')
        return

    df = build_institutional_features(df)

    feature_cols = [
        'er_ratio',
        'atr_ratio',
        'rsi_h1_delta',
        'rsi_m15_delta',
        'adx',
        'rsi_m15',
    ]
    
    # Filter features that exist in the dataframe
    feature_cols = [c for c in feature_cols if c in df.columns]
    target_col = 'target_is_loss'  # 1 nếu lệnh bị cắt lỗ/drawdown, 0 nếu thắng

    if target_col not in df.columns:
        print(f'❌ Không tìm thấy cột nhãn target_col ({target_col}) trong dataset.')
        return

    X = df[feature_cols]
    y = df[target_col]

    # Handle case where target has only 1 class
    if len(np.unique(y)) < 2:
        print(f'⚠️ Tập dữ liệu chỉ có 1 nhãn duy nhất (y={np.unique(y)}). Cần đủ mẫu thắng và thua để huấn luyện ML.')
        return

    # Time-Series Split (Walk-Forward: 5 Folds)
    n_splits = min(5, len(df) // 10)
    if n_splits < 2:
        n_splits = 2
        
    tscv = TimeSeriesSplit(n_splits=n_splits)
    auc_scores = []

    print('===========================================================')
    print('🤖 TIẾN TRÌNH HUẤN LUYỆN WALK-FORWARD XGBOOST GATEKEEPER')
    print('===========================================================')
    print(f'Tải dataset: {len(df)} dòng mẫu | Số đặc trưng: {len(feature_cols)} ({feature_cols})')
    print(f'Số Folds phân chia thời gian (TimeSeriesSplit): {n_splits}')
    print('-----------------------------------------------------------')

    fold = 1
    for train_idx, val_idx in tscv.split(X):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

        # Skip if validation fold has only 1 class
        if len(np.unique(y_val)) < 2 or len(np.unique(y_train)) < 2:
            print(f'Fold {fold} | Train samples: {len(X_train)} | Val samples: {len(X_val)} | OOS AUC: Skipped (Single class)')
            fold += 1
            continue

        # Khởi tạo XGBoost với Hyperparameters nén Overfitting (Chuẩn Fund)
        model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=3,  # Giới hạn cây nông để tránh học vẹt
            learning_rate=0.03,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=1.0,  # L1 Regularization
            reg_lambda=2.0,  # L2 Regularization
            random_state=42,
            eval_metric='auc',
        )

        model.fit(X_train, y_train)
        preds_prob = model.predict_proba(X_val)[:, 1]
        auc = roc_auc_score(y_val, preds_prob)
        auc_scores.append(auc)

        print(
            f'Fold {fold} | Train samples: {len(X_train)} | Val samples:'
            f' {len(X_val)} | OOS AUC: {auc:.4f}'
        )
        fold += 1

    if not auc_scores:
        mean_auc = 0.50
    else:
        mean_auc = np.mean(auc_scores)
        
    print('-----------------------------------------------------------')
    print(f'🎯 AUC Trung bình trên tập Out-of-Sample (OOS): {mean_auc:.4f}')

    if mean_auc >= 0.55:
        print(
            '🟢 Mô hình đạt độ phân giải Alpha chuẩn. Đang xuất file'
            ' gatekeeper_v1.json...'
        )
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
        os.makedirs('src/ml', exist_ok=True)
        final_model.save_model('src/ml/gatekeeper_v1.json')
        print(
            '✅ Đã nạp thành công mô hình mới vào:'
            ' src/ml/gatekeeper_v1.json'
        )
    else:
        print(
            '🟡 AUC chưa đạt kỳ vọng (>=0.55). Giữ nguyên mô hình hiện tại để'
            ' thu thập thêm dữ liệu.'
        )

if __name__ == '__main__':
    run_walk_forward_training()
