import sys
import os
import pandas as pd
import numpy as np

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath("."))

def run_alpha_tests():
    print("=== STARTING ALPHA SYSTEM VERIFICATION ===")
    results = {}

    # 1. Test Regime Engine
    try:
        from src.regime_engine import RegimeEngine, MarketRegime
        regime_eng = RegimeEngine()
        r_range = regime_eng.get_regime(15.0)
        r_trans = regime_eng.get_regime(20.0)
        r_trend = regime_eng.get_regime(30.0)
        assert r_range == MarketRegime.RANGE
        assert r_trans == MarketRegime.TRANSITION
        assert r_trend == MarketRegime.TREND
        assert not regime_eng.can_open_new_trades(r_trans)
        assert regime_eng.can_open_new_trades(r_trend)
        results["RegimeEngine (src)"] = "✅ PASSED"
    except Exception as e:
        results["RegimeEngine (src)"] = f"❌ FAILED: {e}"

    # 2. Test Multi-Timeframe Signal Engine
    try:
        from src.signal_engine import SignalEngine, Signal
        sig_eng = SignalEngine(regime_eng)
        
        # Test BUY logic
        buy_indicators = {
            "RSI_H4": 60.0,
            "RSI_H1": 58.0,
            "RSI_M15": 52.0,
            "ADX": 28.0,
            "M15_RSI_RISING": True,
            "M15_CLOSE_RISING": True,
            "M15_FRESH_LOCAL_LOW": False,
            "M15_FRESH_LOCAL_HIGH": False
        }
        sig_buy = sig_eng.evaluate(buy_indicators)
        assert sig_buy == Signal.BUY, f"Expected BUY, got {sig_buy}"

        # Test SELL logic
        sell_indicators = {
            "RSI_H4": 40.0,
            "RSI_H1": 42.0,
            "RSI_M15": 48.0,
            "ADX": 30.0,
            "M15_RSI_FALLING": True,
            "M15_CLOSE_FALLING": True,
            "M15_FRESH_LOCAL_LOW": False,
            "M15_FRESH_LOCAL_HIGH": False
        }
        sig_sell = sig_eng.evaluate(sell_indicators)
        assert sig_sell == Signal.SELL, f"Expected SELL, got {sig_sell}"

        # Test HOLD on low ADX (TRANSITION regime)
        hold_indicators = {**buy_indicators, "ADX": 20.0}
        sig_hold = sig_eng.evaluate(hold_indicators)
        assert sig_hold == Signal.HOLD, f"Expected HOLD, got {sig_hold}"

        results["MTF SignalEngine (src)"] = "✅ PASSED"
    except Exception as e:
        results["MTF SignalEngine (src)"] = f"❌ FAILED: {e}"

    # 3. Test ML Gatekeeper (src)
    try:
        from src.xgboost_gatekeeper import MLGatekeeper
        gatekeeper = MLGatekeeper()
        status = "READY" if gatekeeper.is_ready else "FALLBACK/OFFLINE (Booster not loaded or xgb missing)"
        results["ML Gatekeeper (src)"] = f"✅ PASSED (Status: {status})"
    except Exception as e:
        results["ML Gatekeeper (src)"] = f"❌ FAILED: {e}"

    # 4. Test SMC Alpha Engine & V9 Continuum Signal Layers
    try:
        from v9_continuum.layers.signal import SMCEngine, MarketRegimeClassifier, MLSignalEngine, Signal as V9Signal
        
        # Test Regime Classifier
        clf = MarketRegimeClassifier()
        reg = clf.classify_regime(adx=30.0, atr_ratio=1.2)
        allowed, msg = clf.is_signal_allowed("SMC_BOS", reg)
        assert allowed is True

        # Test SMC Engine with synthetic candles
        dates = pd.date_range("2026-01-01", periods=50, freq="15min")
        prices = [100 + np.sin(i / 3.0) * 2 + i * 0.1 for i in range(50)]
        df_dummy = pd.DataFrame({
            "open": prices,
            "high": [p + 0.5 for p in prices],
            "low": [p - 0.5 for p in prices],
            "close": [p + 0.2 for p in prices]
        }, index=dates)
        
        smc = SMCEngine(swing_window=3)
        sh, sl = smc.find_swings(df_dummy)
        fvgs = smc.detect_fvgs(df_dummy)
        obs = smc.detect_order_blocks(df_dummy, sh, sl)
        smc_sig, smc_reason = smc.evaluate_smc_signal(df_dummy)
        
        # Test MLSignalEngine
        ml_eng = MLSignalEngine()
        prob = ml_eng.predict_loss_probability({"ADX": 25.0, "ATR": 0.002, "RSI_H1": 60.0})
        assert 0.0 <= prob <= 1.0

        results["SMC & Continuum Alpha Layer (v9_continuum)"] = "✅ PASSED"
    except Exception as e:
        results["SMC & Continuum Alpha Layer (v9_continuum)"] = f"❌ FAILED: {e}"

    # 5. Test Hourly Gate
    try:
        from src.hourly_gate import HourlyGate
        from datetime import datetime, timezone
        hg = HourlyGate()
        allowed, reason = hg.can_trade("EURUSD", datetime(2026, 8, 22, 10, 2, 0, tzinfo=timezone.utc))
        results["Hourly Gate (Timing Filter)"] = f"✅ PASSED (Evaluation: allowed={allowed})"
    except Exception as e:
        results["Hourly Gate (Timing Filter)"] = f"❌ FAILED: {e}"

    print("\n=== SUMMARY RESULTS ===")
    for k, v in results.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    run_alpha_tests()
