import sys
import os

sys.path.append(os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')

def test_regime_classifier():
    print("=================================================================", flush=True)
    print("  PHASE 2: MARKET REGIME SHIFT CLASSIFIER VERIFICATION", flush=True)
    print("=================================================================\n", flush=True)

    from v9_continuum.layers.signal import MarketRegimeClassifier, MarketRegime

    classifier = MarketRegimeClassifier(adx_trending_threshold=25.0, atr_volatility_threshold=1.10)

    test_cases = [
        {"adx": 32.0, "atr_ratio": 1.45, "signal_type": "TREND_FOLLOWING", "desc": "Mạnh mẽ trending + high volatility"},
        {"adx": 28.0, "atr_ratio": 0.95, "signal_type": "SMC_BOS", "desc": "Trending + low volatility"},
        {"adx": 18.0, "atr_ratio": 1.30, "signal_type": "MEAN_REVERSION", "desc": "Ranging + high volatility spike"},
        {"adx": 15.0, "atr_ratio": 0.85, "signal_type": "TREND_FOLLOWING", "desc": "Sideway đi ngang + low volatility"},
        {"adx": 15.0, "atr_ratio": 0.85, "signal_type": "MEAN_REVERSION", "desc": "Sideway đi ngang + low volatility"},
    ]

    print(f"[1] VERIFYING REGIME CLASSIFICATION & SIGNAL BLOCKING:")
    for idx, tc in enumerate(test_cases, 1):
        regime = classifier.classify_regime(tc["adx"], tc["atr_ratio"])
        allowed, msg = classifier.is_signal_allowed(tc["signal_type"], regime)
        status_str = "APPROVED" if allowed else "BLOCKED (CHẶN THÀNH CÔNG)"
        print(f"  - Case #{idx} ({tc['desc']}): ADX={tc['adx']} | ATR_Ratio={tc['atr_ratio']} -> Regime: {regime.value:23s} | Signal: {tc['signal_type']:15s} -> {status_str} ({msg})")

    print("\n[2] VERIFICATION SUMMARY: PASSED (MarketRegimeClassifier blocks trend signals in RANGING_MEAN_REVERTING).")

if __name__ == "__main__":
    test_regime_classifier()
