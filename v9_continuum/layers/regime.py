import numpy as np
import pandas as pd
from enum import Enum
from typing import Tuple, Optional, Dict, Any

try:
    from hmmlearn.hmm import GaussianHMM
    HMM_AVAILABLE = True
except ImportError:
    GaussianHMM = None
    HMM_AVAILABLE = False


class MarketRegime(Enum):
    ACCUMULATION = "ACCUMULATION"  # Ranging / Mean Reversion
    EXPANSION = "EXPANSION"        # Trending / Momentum
    UNKNOWN = "UNKNOWN"


# ── Asia Session: OU Process + Kalman Filter ──────────────────────

def fit_ou_process(prices: np.ndarray) -> Tuple[float, float, float]:
    """
    Fits an Ornstein-Uhlenbeck process to price data.
    SDE: dXt = theta * (mu - Xt) * dt + sigma * dWt
    Returns: (theta, mu, sigma)
    """
    if len(prices) < 3:
        return 0.0, 0.0, 0.0
    
    # x_t = X_{t-1}, y_t = X_t - X_{t-1}
    x = prices[:-1]
    y = np.diff(prices)
    
    # Fit linear regression: y = a + b*x + e
    n = len(x)
    sum_x = np.sum(x)
    sum_y = np.sum(y)
    sum_xx = np.sum(x**2)
    sum_xy = np.sum(x * y)
    
    denom = (n * sum_xx - sum_x**2)
    if abs(denom) < 1e-12:
        return 0.0, 0.0, 0.0
        
    b = (n * sum_xy - sum_x * sum_y) / denom
    a = (sum_y - b * sum_x) / n
    
    # Map back to OU parameters (assuming dt = 1)
    theta = -b
    if theta <= 0:
        # Not mean reverting
        mu = np.mean(prices)
    else:
        mu = -a / b
        
    residuals = y - (a + b * x)
    sigma = np.std(residuals)
    
    return float(theta), float(mu), float(sigma)


class KalmanFilterTracker:
    """
    1D Kalman Filter to track underlying asset price state.
    """
    def __init__(self, q: float = 1e-4, r: float = 1e-2):
        self.q = q  # Process noise covariance
        self.r = r  # Measurement noise covariance
        self.x = None  # State estimate (smoothed price)
        self.p = 1.0   # State covariance

    def update(self, z: float) -> Tuple[float, float]:
        """
        Updates the Kalman state with a new measurement z.
        Returns: (state estimate, Z-score)
        """
        if self.x is None:
            self.x = z
            return self.x, 0.0
            
        # Predict step
        x_pred = self.x
        p_pred = self.p + self.q
        
        # Update step
        residual = z - x_pred
        s = p_pred + self.r
        k = p_pred / s  # Kalman Gain
        
        self.x = x_pred + k * residual
        self.p = (1 - k) * p_pred
        
        # Z-score computation
        z_score = residual / np.sqrt(s)
        return self.x, float(z_score)


# ── Europe Session: HMM / Volatility Fallback ─────────────────────

class EuropeRegimeDetector:
    """
    Classifies European sessions using HMM (Hidden Markov Model)
    into ACCUMULATION and EXPANSION.
    Falls back to Volatility range comparison if hmmlearn is not installed.
    """
    def __init__(self, n_components: int = 2):
        self.n_components = n_components

    def detect_regime(self, returns: np.ndarray) -> MarketRegime:
        """
        Detect regime based on historical returns.
        """
        if len(returns) < 30:
            return MarketRegime.UNKNOWN
            
        if HMM_AVAILABLE and GaussianHMM is not None:
            try:
                # Fit 2-state HMM
                model = GaussianHMM(n_components=self.n_components, covariance_type="diag", n_iter=100, random_state=42)
                # Reshape returns for fitting
                obs = returns.reshape(-1, 1)
                model.fit(obs)
                
                # Predict current state
                states = model.predict(obs)
                current_state = int(states[-1])
                
                # Enforce state ordering: index 0 should be low-variance (Accumulation)
                # index 1 should be high-variance (Expansion)
                covars = np.squeeze(model.covars_)
                if covars[0] > covars[1]:
                    # Swap states mapping
                    current_state = 1 - current_state
                    
                return MarketRegime.ACCUMULATION if current_state == 0 else MarketRegime.EXPANSION
            except Exception:
                # Fallback on HMM failure
                pass

        # Volatility Fallback
        df = pd.Series(returns)
        vol = df.rolling(window=10).std().dropna().values
        if len(vol) < 2:
            return MarketRegime.UNKNOWN
        
        current_vol = vol[-1]
        median_vol = np.median(vol)
        
        # If current volatility is above median, classify as EXPANSION
        if current_vol > median_vol * 1.2:
            return MarketRegime.EXPANSION
        return MarketRegime.ACCUMULATION


# ── US Session: KAMA + ADX ────────────────────────────────────────

def calculate_kama(prices: pd.Series, period: int = 10, fast: int = 2, slow: int = 30) -> pd.Series:
    """
    Calculates Kaufman's Adaptive Moving Average.
    """
    change = (prices - prices.shift(period)).abs()
    volatility = (prices - prices.shift(1)).abs().rolling(window=period).sum()
    
    er = change / volatility
    er = er.fillna(0.0)
    
    sc_fast = 2.0 / (fast + 1)
    sc_slow = 2.0 / (slow + 1)
    
    sc = (er * (sc_fast - sc_slow) + sc_slow) ** 2
    
    kama = pd.Series(index=prices.index, dtype=float)
    
    # Seed KAMA with first value
    first_valid = sc.first_valid_index()
    if first_valid is None:
        return kama.fillna(prices)
        
    kama.loc[first_valid] = prices.loc[first_valid]
    
    for i in range(prices.index.get_loc(first_valid) + 1, len(prices)):
        idx = prices.index[i]
        prev_idx = prices.index[i-1]
        kama.loc[idx] = kama.loc[prev_idx] + sc.loc[idx] * (prices.loc[idx] - kama.loc[prev_idx])
        
    return kama


def calculate_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculates Average Directional Index (ADX) in pure Python/Pandas.
    """
    prev_close = close.shift(1)
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    # Wilder's Smoothing
    tr_smooth = tr.rolling(window=period).mean() # Fallback approximation
    plus_dm_smooth = pd.Series(plus_dm, index=high.index).rolling(window=period).mean()
    minus_dm_smooth = pd.Series(minus_dm, index=high.index).rolling(window=period).mean()
    
    # Recalculate using Wilder's smoothing logic if needed, but rolling mean is highly stable
    plus_di = 100 * (plus_dm_smooth / tr_smooth)
    minus_di = 100 * (minus_dm_smooth / tr_smooth)
    
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).fillna(1.0))
    adx = dx.rolling(window=period).mean()
    
    return adx.fillna(0.0)


def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculates the Relative Strength Index (RSI).
    """
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)
