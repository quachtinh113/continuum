import pytest
from config import settings

@pytest.fixture(autouse=True, scope="function")
def configure_test_settings():
    """Autouse fixture to isolate settings to standard test defaults."""
    # Save original values
    originals = {
        "MAX_LOT_SIZE": getattr(settings, "MAX_LOT_SIZE", 0.01),
        "MAX_DAILY_DRAWDOWN_USD": getattr(settings, "MAX_DAILY_DRAWDOWN_USD", 50.0),
        "BREAK_EVEN_ACTIVATION_ATR_MULTIPLIER": getattr(settings, "BREAK_EVEN_ACTIVATION_ATR_MULTIPLIER", 0.75),
        "BREAK_EVEN_BUFFER_ATR_MULTIPLIER": getattr(settings, "BREAK_EVEN_BUFFER_ATR_MULTIPLIER", 0.0),
        "FX_BASE_LOT": getattr(settings, "FX_BASE_LOT", 0.01),
        "COMMODITY_BASE_LOT": getattr(settings, "COMMODITY_BASE_LOT", 0.01),
        "CRYPTO_BASE_LOT": getattr(settings, "CRYPTO_BASE_LOT", 0.01),
        "RISK_PER_TRADE_PERCENT": getattr(settings, "RISK_PER_TRADE_PERCENT", 0.1),
    }
    
    # Apply standard test values
    settings.MAX_LOT_SIZE = 0.01
    settings.MAX_DAILY_DRAWDOWN_USD = 50.0
    settings.BREAK_EVEN_ACTIVATION_ATR_MULTIPLIER = 0.75
    settings.BREAK_EVEN_BUFFER_ATR_MULTIPLIER = 0.0
    settings.FX_BASE_LOT = 0.01
    settings.COMMODITY_BASE_LOT = 0.01
    settings.CRYPTO_BASE_LOT = 0.01
    settings.RISK_PER_TRADE_PERCENT = 0.1

    yield

    # Restore original values after test runs
    for attr, val in originals.items():
        setattr(settings, attr, val)
