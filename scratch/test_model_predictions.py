import sys
import os
import xgboost as xgb
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def inspect_model():
    model_path = PROJECT_ROOT / "src" / "ml" / "gatekeeper_v1.model"
    print(f"Loading model from: {model_path}")
    
    if not model_path.exists():
        print("Model file does not exist!")
        return
        
    model = xgb.Booster()
    model.load_model(str(model_path))
    
    cols = ['RSI_Delta', 'Volatility_Index', 'Session_Code', 'RSI_H1_Div', 'Trend_Vol_Ratio', 'RSI_M15', 'RSI_H1', 'RSI_H4', 'ADX', 'ATR', 'hour']
    
    # 1. Feature set from AUDUSD logs (Normalized)
    # Volatility_Index = 0.00071
    # ATR = 0.00071 (Normalized)
    # Trend_Vol_Ratio = ADX * Volatility_Index = 40.62 * 0.00071 = 0.0288
    feat1 = {
        "RSI_Delta": -21.64,
        "Volatility_Index": 0.00071,
        "Session_Code": 1.0, # EUROPE
        "RSI_H1_Div": 22.77,
        "Trend_Vol_Ratio": 0.0288,
        "RSI_M15": 37.89,
        "RSI_H1": 27.23,
        "RSI_H4": 16.25,
        "ADX": 40.62,
        "ATR": 0.00071,
        "hour": 12.0
    }
    
    # 2. Good Trend Features (Normalized)
    feat2 = {
        "RSI_Delta": 5.0,
        "Volatility_Index": 0.0001,
        "Session_Code": 2.0, # US
        "RSI_H1_Div": 5.0,
        "Trend_Vol_Ratio": 0.0035,
        "RSI_M15": 48.0,
        "RSI_H1": 52.0,
        "RSI_H4": 53.0,
        "ADX": 35.0,
        "ATR": 0.0001,
        "hour": 15.0
    }

    # 3. High risk/Overbought Features (Normalized)
    feat3 = {
        "RSI_Delta": -35.0,
        "Volatility_Index": 0.005,
        "Session_Code": 1.0,
        "RSI_H1_Div": 30.0,
        "Trend_Vol_Ratio": 0.275,
        "RSI_M15": 85.0,
        "RSI_H1": 80.0,
        "RSI_H4": 50.0,
        "ADX": 55.0,
        "ATR": 0.005,
        "hour": 10.0
    }

    for name, feat in [("AUDUSD Log Features", feat1), ("Good Trend Features", feat2), ("Extreme High Risk Features", feat3)]:
        row = [feat.get(col, 0.0) for col in cols]
        dtest = xgb.DMatrix([row], feature_names=cols)
        prob = model.predict(dtest)[0]
        print(f"\nPrediction for {name}:")
        print(f"  Inputs: {feat}")
        print(f"  Predicted Loss Probability: {prob:.4f}")

if __name__ == "__main__":
    inspect_model()
