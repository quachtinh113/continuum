import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import accuracy_score, precision_score
import os

def load_data():
    df = pd.read_csv('logs/training_data.csv')
    df['entry_time'] = pd.to_datetime(df['entry_time'])
    
    # 2. Feature Engineering
    # Define RSI_Delta
    df['RSI_Delta'] = df['RSI_H4'] - df['RSI_M15']
    
    # Load historical CSVs in memory once
    symbols = df['symbol'].unique()
    hist_cache = {}
    for symbol in symbols:
        hist_file = f'data/historical/{symbol}_M15.csv'
        if os.path.exists(hist_file):
            hist_df = pd.read_csv(hist_file)
            hist_df['time'] = pd.to_datetime(hist_df['time'], utc=True)
            hist_df = hist_df.sort_values('time')
            hist_cache[symbol] = hist_df

    prices = []
    for idx, row in df.iterrows():
        symbol = row['symbol']
        time = row['entry_time']
        hist_df = hist_cache.get(symbol)
        if hist_df is not None and not hist_df.empty:
            # Quick lookup using searchsorted
            times = hist_df['time']
            pos = times.searchsorted(time)
            if pos == 0:
                price = hist_df.iloc[0]['close']
            elif pos >= len(hist_df):
                price = hist_df.iloc[-1]['close']
            else:
                before = hist_df.iloc[pos-1]
                after = hist_df.iloc[pos]
                if abs(before['time'] - time) < abs(after['time'] - time):
                    price = before['close']
                else:
                    price = after['close']
            prices.append(price)
        else:
            prices.append(np.nan)
            
    df['Price'] = prices
    
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

    approx_prices = df["symbol"].apply(get_approx_price)
    df['Price'] = df['Price'].fillna(approx_prices)
    
    # Volatility_Index = ATR / Price
    df['Volatility_Index'] = df['ATR'] / df['Price']
    
    # Engineered features for quant risk enhancements
    session_map = {"ASIA": 0, "EUROPE": 1, "US": 2, "OVERLAP_ASIA_EU": 3, "OVERLAP_EU_US": 4, "OFF": -1}
    df["Session_Code"] = df["session"].map(session_map).fillna(-1)
    df["RSI_H1_Div"] = (df["RSI_H1"] - 50.0).abs()
    df["Trend_Vol_Ratio"] = df["ADX"] * df["ATR"]
    
    # Drop NaNs
    features = ['RSI_Delta', 'Volatility_Index', 'Session_Code', 'RSI_H1_Div', 'Trend_Vol_Ratio', 'RSI_M15', 'RSI_H1', 'RSI_H4', 'ADX', 'ATR', 'hour']
    df = df.dropna(subset=features)
    
    return df, features

def train():
    df, feature_cols = load_data()
    print(f"Loaded {len(df)} rows for training.")
    
    # 3. Train XGBoost to classify PROFITABLE vs LOSS_THREAT
    # is_win: 1 = PROFITABLE, 0 = LOSS_THREAT.
    # y = 1 - is_win (1 = LOSS_THREAT, 0 = PROFITABLE)
    X = df[feature_cols]
    y = 1 - df['is_win']
    
    # 6. Validation: Cross-validation
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    acc_scores = []
    prec_scores = []
    
    for train_idx, test_idx in skf.split(X, y):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        
        clf = xgb.XGBClassifier(
            max_depth=4,
            learning_rate=0.1,
            n_estimators=100,
            objective='binary:logistic',
            eval_metric='auc',
            use_label_encoder=False,
            random_state=42
        )
        clf.fit(X_train, y_train)
        
        preds = clf.predict(X_test)
        acc_scores.append(accuracy_score(y_test, preds))
        prec_scores.append(precision_score(y_test, preds, zero_division=0))
        
    print(f"--- Cross-Validation Results ---")
    print(f"Accuracy:  {np.mean(acc_scores):.4f}")
    print(f"Precision: {np.mean(prec_scores):.4f}")
    
    # Train final model on all data
    final_model = xgb.XGBClassifier(
        max_depth=4,
        learning_rate=0.1,
        n_estimators=100,
        objective='binary:logistic',
        eval_metric='auc',
        use_label_encoder=False,
        random_state=42
    )
    final_model.fit(X, y)
    
    # 4. Feature Importance
    importance = final_model.feature_importances_
    imp_dict = dict(zip(feature_cols, importance))
    sorted_imp = sorted(imp_dict.items(), key=lambda x: x[1], reverse=True)
    
    print("\n--- Feature Importance ---")
    for feat, imp in sorted_imp:
        print(f"{feat}: {imp:.4f}")
        
    print(f"\nFeature contributing most to LOSS_THREAT: {sorted_imp[0][0]}")
    
    # 5. Save model
    model_path = 'src/ml/gatekeeper_v1.model'
    # Ensure dir exists
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    final_model.get_booster().save_model(model_path)
    print(f"\nModel saved to {model_path}")

if __name__ == "__main__":
    train()
