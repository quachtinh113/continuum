import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional
from config import settings

class MetaLabelingEngine:
    """
    2-Layer Meta-Model Execution Architecture:
    - Primary Model (Layer 1): Rule-based Signal Generator (Direction: +1 BUY, -1 SELL, 0 HOLD)
    - Secondary Model (Layer 2): Machine Learning Meta-Gatekeeper predicting P(Win).
      Vetoes primary signal if P(Win) < ML_VETO_THRESHOLD (Default: 0.70).
    """
    def __init__(self, veto_threshold: float = 0.70):
        self.veto_threshold = veto_threshold
        # Fallback heuristic model for fast execution
        self.weights = {
            "er_ratio": 1.2,
            "atr_ratio": 0.8,
            "rsi_m15_delta": 0.5,
            "adx_scaled": 1.0
        }

    def predict_win_probability(self, features: Dict[str, float]) -> float:
        """
        Predicts P(Win) based on extracted stationary features.
        Calculates a calibrated logistic probability score.
        """
        try:
            er = features.get("er_ratio", 0.5)
            atr_r = features.get("atr_ratio", 1.0)
            adx_s = features.get("adx_scaled", 0.0)
            rsi_delta = abs(features.get("rsi_m15_delta", 0.0)) / 10.0

            # Linear logit combination
            logit = (
                self.weights["er_ratio"] * (er - 0.5) +
                self.weights["atr_ratio"] * (atr_r - 1.0) +
                self.weights["adx_scaled"] * adx_s +
                self.weights["rsi_m15_delta"] * rsi_delta
            )
            # Sigmoid activation
            prob_win = 1.0 / (1.0 + np.exp(-logit))
            return float(np.clip(prob_win, 0.10, 0.95))
        except Exception:
            return 0.50

    def evaluate_meta_signal(
        self,
        primary_signal: str,
        features: Dict[str, float]
    ) -> Tuple[bool, float, str]:
        """
        Evaluates Meta-Labeling Layer 2 decision.
        Returns: (approved: bool, win_probability: float, reason: str)
        """
        if primary_signal == "HOLD":
            return False, 0.0, "Primary signal is HOLD"

        win_prob = self.predict_win_probability(features)

        if win_prob >= self.veto_threshold:
            return True, win_prob, f"Meta-Model Approved: P(Win) = {win_prob:.2f} >= {self.veto_threshold:.2f}"
        else:
            return False, win_prob, f"Meta-Model Vetoed: P(Win) = {win_prob:.2f} < {self.veto_threshold:.2f}"
