import sys, os
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.audit_logger import log_decision, log_info
from config import settings

print(f"settings.LOG_PATH: {settings.LOG_PATH}")
print(f"Does LOG_PATH exist? {settings.LOG_PATH.exists()}")

class MockRiskDecision:
    def __init__(self):
        self.severity = "INFO"
        self.status_str = "APPROVED"
        self.reason = "Test decision"

indicators = {
    "RSI_H4": 50.0,
    "RSI_H1": 50.0,
    "RSI_M15": 50.0,
    "ADX": 20.0,
    "ATR": 0.001
}

print("Logging decision...")
res = log_decision("EURUSD", "ASIA", indicators, "BUY", MockRiskDecision(), "ROUTE")
print(f"Result: {res}")

today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
expected_file = settings.LOG_PATH / f"audit_{today}.jsonl"
print(f"Expected file: {expected_file}")
print(f"Does expected file exist? {expected_file.exists()}")
