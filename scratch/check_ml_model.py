import os
import sys

# Add workspace root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from v9_continuum.layers.signal import MLSignalEngine

def main():
    engine = MLSignalEngine()
    print(f"ML Model Ready: {engine.is_ready}")
    print(f"Model Path: {engine.model_path}")
    print(f"Model Object: {engine.model}")
    
    # Test prediction
    dummy_feat = {
        "er_ratio": 0.5,
        "atr_ratio": 1.0,
        "rsi_h1_delta": 0.0,
        "rsi_m15_delta": 0.0,
        "adx": 20.0,
        "rsi_m15": 50.0,
        "RSI_M15": 50.0,
        "RSI_H1": 50.0,
        "RSI_H4": 50.0,
        "ADX": 20.0,
        "ATR": 0.002,
        "RSI_Delta": 0.0,
        "Volatility_Index": 0.002 / 1.0,
        "hour": 10,
        "Session_Code": 1,
        "RSI_H1_Div": 0.0,
        "Trend_Vol_Ratio": 20.0 * 0.002
    }
    prob = engine.predict_loss_probability(dummy_feat)
    print(f"Predicted loss prob: {prob}")

if __name__ == '__main__':
    main()
