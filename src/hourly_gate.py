"""
NowTrading 2.1 — Hourly Gate (Build Step 3)
Controls trade entry timing: one trade per symbol per hour at even-hour marks.

Constitution §4:
- Chỉ xét lệnh tại khung giờ chẵn
- Không overtrade trong cùng 1 giờ
- Mỗi symbol chỉ được mở 1 trade cycle chính trong 1 hourly bucket
"""

from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from config import settings
from src.audit_logger import log_info


class HourlyGate:
    """
    Hourly Gate controls trade entry timing.

    Rules:
    - Only allow trade entry within first N minutes of each hour
    - Only one trade per symbol per hourly bucket
    - Track trade history to prevent duplicates
    """

    def __init__(self, window_minutes: int = None):
        self.window_minutes = window_minutes or settings.HOURLY_GATE_WINDOW_MINUTES
        # Track: symbol → last trade hour (YYYY-MM-DD HH)
        self._trade_log: Dict[str, str] = {}

    def can_trade(
        self,
        symbol: str,
        current_time: Optional[datetime] = None,
    ) -> Tuple[bool, str]:
        """
        Check if a new trade is allowed for this symbol at this time.

        Args:
            symbol: Symbol key
            current_time: Current UTC time (uses now if None)

        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        # EMERGENCY EVENT MODE BYPASS (§8)
        if settings.EMERGENCY_EVENT_MODE:
            # Skip time window rules, but still enforce no duplicate trade in the same hour
            pass
        else:
            # Rule 1: No trade during first 60 seconds of new hour (§8)
            if current_time.minute == 0:
                return (
                    False,
                    "First 60 seconds cooldown"
                )
                
            # Rule 2: Must be within the hourly gate window (minutes 1 to N-1)
            if current_time.minute >= self.window_minutes:
                return (
                    False,
                    f"Outside gate window: minute {current_time.minute} >= {self.window_minutes}"
                )

        # Rule 3: No duplicate trade in same hourly bucket
        hour_bucket = self._get_hour_bucket(current_time)
        last_bucket = self._trade_log.get(symbol)

        if last_bucket == hour_bucket:
            return (
                False,
                f"Already traded {symbol} in bucket {hour_bucket}"
            )

        return (True, "Gate open")

    def record_trade(
        self,
        symbol: str,
        current_time: Optional[datetime] = None,
    ):
        """
        Record that a trade was placed for this symbol at this time.

        Args:
            symbol: Symbol key
            current_time: Current UTC time (uses now if None)
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        hour_bucket = self._get_hour_bucket(current_time)
        self._trade_log[symbol] = hour_bucket
        log_info(f"Hourly Gate │ Recorded trade for {symbol} in bucket {hour_bucket}")

    def reset(self, symbol: Optional[str] = None):
        """
        Reset gate tracking for one or all symbols.

        Args:
            symbol: If provided, reset only this symbol. Otherwise reset all.
        """
        if symbol:
            self._trade_log.pop(symbol, None)
        else:
            self._trade_log.clear()

    def get_status(self) -> Dict[str, str]:
        """Get current gate status for all tracked symbols."""
        return dict(self._trade_log)

    @staticmethod
    def _get_hour_bucket(dt: datetime) -> str:
        """
        Get hourly bucket identifier.

        Format: "YYYY-MM-DD HH" (e.g. "2025-01-15 14")
        """
        return dt.strftime("%Y-%m-%d %H")
