import sys
import os
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.session_manager import get_weekend_liquidation_phase
from config import settings

def test_phases():
    print("======================================================")
    print("Testing Weekend Liquidation Engine 3-Phase Detection")
    print("======================================================")
    
    # Enable setting for testing
    settings.ENABLE_WEEKEND_LIQUIDATION = True
    settings.LIQUIDATION_HOUR_UTC = 20
    
    # 1. Monday 12:00 UTC (Should be phase 0)
    dt_monday = datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc)
    phase = get_weekend_liquidation_phase(dt_monday, settings.LIQUIDATION_HOUR_UTC)
    print(f"Monday 12:00 UTC -> Phase {phase} (Expected: 0) | {'PASSED' if phase == 0 else 'FAILED'}")
    
    # 2. Friday 17:59 UTC (Should be phase 0)
    dt_friday_1 = datetime(2026, 7, 3, 17, 59, 0, tzinfo=timezone.utc)
    phase = get_weekend_liquidation_phase(dt_friday_1, settings.LIQUIDATION_HOUR_UTC)
    print(f"Friday 17:59 UTC -> Phase {phase} (Expected: 0) | {'PASSED' if phase == 0 else 'FAILED'}")

    # 3. Friday 18:05 UTC (Should be phase 1 - Block entries)
    dt_friday_2 = datetime(2026, 7, 3, 18, 5, 0, tzinfo=timezone.utc)
    phase = get_weekend_liquidation_phase(dt_friday_2, settings.LIQUIDATION_HOUR_UTC)
    print(f"Friday 18:05 UTC -> Phase {phase} (Expected: 1) | {'PASSED' if phase == 1 else 'FAILED'}")

    # 4. Friday 19:35 UTC (Should be phase 2 - Cancel pending/DCA)
    dt_friday_3 = datetime(2026, 7, 3, 19, 35, 0, tzinfo=timezone.utc)
    phase = get_weekend_liquidation_phase(dt_friday_3, settings.LIQUIDATION_HOUR_UTC)
    print(f"Friday 19:35 UTC -> Phase {phase} (Expected: 2) | {'PASSED' if phase == 2 else 'FAILED'}")

    # 5. Friday 20:05 UTC (Should be phase 3 - Close positions)
    dt_friday_4 = datetime(2026, 7, 3, 20, 5, 0, tzinfo=timezone.utc)
    phase = get_weekend_liquidation_phase(dt_friday_4, settings.LIQUIDATION_HOUR_UTC)
    print(f"Friday 20:05 UTC -> Phase {phase} (Expected: 3) | {'PASSED' if phase == 3 else 'FAILED'}")

if __name__ == "__main__":
    test_phases()
