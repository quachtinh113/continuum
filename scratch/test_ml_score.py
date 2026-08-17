import sys
from pathlib import Path

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding='utf-8')

from src.xgboost_gatekeeper import MLGatekeeper

gk = MLGatekeeper()
if gk.is_ready:
    print("ML Gatekeeper model loaded.")
    # Test US100 00:00:27 signal: RSI_H4=67.18, RSI_H1=61.61, RSI_M15=56.26, ADX=40.59, ATR=0.001971, price=29731.07
    indicators_1 = {'RSI_M15': 56.26, 'RSI_H1': 61.61, 'RSI_H4': 67.18, 'ADX': 40.59, 'ATR': 0.001971}
    score_1 = gk.score_trade(indicators_1, price=29731.07, hour=0, session="ASIA")
    print(f"US100 #1 Loss Threat Score: {score_1}")

    # Test US100 01:10:21 signal: RSI_H4=67.18, RSI_H1=59.03, RSI_M15=49.7, ADX=41.91, ATR=0.002, price=29737.56
    indicators_2 = {'RSI_M15': 49.7, 'RSI_H1': 59.03, 'RSI_H4': 67.18, 'ADX': 41.91, 'ATR': 0.002}
    score_2 = gk.score_trade(indicators_2, price=29737.56, hour=1, session="ASIA")
    print(f"US100 #2 Loss Threat Score: {score_2}")

    # Test US100 02:20:20 signal: RSI_H4=67.18, RSI_H1=63.9, RSI_M15=57.96, ADX=42.63, ATR=0.002166, price=29773.81
    indicators_3 = {'RSI_M15': 57.96, 'RSI_H1': 63.9, 'RSI_H4': 67.18, 'ADX': 42.63, 'ATR': 0.002166}
    score_3 = gk.score_trade(indicators_3, price=29773.81, hour=2, session="ASIA")
    print(f"US100 #3 Loss Threat Score: {score_3}")
else:
    print("ML Gatekeeper not ready or model file missing.")
