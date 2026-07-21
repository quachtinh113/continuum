"""
NowTrading 2.1 — Session Manager
Detects current trading session (Asia, Europe, US) based on UTC time.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class Session(Enum):
    """Trading session identifiers."""
    ASIA = "ASIA"
    EUROPE = "EUROPE"
    US = "US"
    OVERLAP_ASIA_EU = "OVERLAP_ASIA_EU"
    OVERLAP_EU_US = "OVERLAP_EU_US"
    OFF = "OFF"


# ── Session Time Ranges (UTC hours) ────────────────────────
# Asia:   00:00 - 09:00 UTC
# Europe: 07:00 - 16:00 UTC
# US:     13:00 - 22:00 UTC
#
# Overlaps:
#   Asia-Europe: 07:00 - 09:00 UTC
#   Europe-US:   13:00 - 16:00 UTC

_SESSION_RANGES = {
    Session.ASIA:   (0, 9),
    Session.EUROPE: (7, 16),
    Session.US:     (13, 22),
}


def get_current_session(utc_time: Optional[datetime] = None) -> Session:
    """
    Determine the current trading session based on UTC time.

    Returns the most specific session (overlap sessions take priority).

    Args:
        utc_time: UTC datetime. Uses current UTC time if None.

    Returns:
        Session enum value.
    """
    if utc_time is None:
        utc_time = datetime.now(timezone.utc)

    hour = utc_time.hour

    in_asia = _SESSION_RANGES[Session.ASIA][0] <= hour < _SESSION_RANGES[Session.ASIA][1]
    in_europe = _SESSION_RANGES[Session.EUROPE][0] <= hour < _SESSION_RANGES[Session.EUROPE][1]
    in_us = _SESSION_RANGES[Session.US][0] <= hour < _SESSION_RANGES[Session.US][1]

    # Check overlaps first (more specific)
    if in_europe and in_us:
        return Session.OVERLAP_EU_US
    if in_asia and in_europe:
        return Session.OVERLAP_ASIA_EU

    # Single sessions
    if in_asia:
        return Session.ASIA
    if in_europe:
        return Session.EUROPE
    if in_us:
        return Session.US

    return Session.OFF


def is_weekend(utc_time: Optional[datetime] = None) -> bool:
    """
    Check if the Forex market is closed for the weekend.

    Forex market closes Friday ~22:00 UTC and reopens Sunday ~22:00 UTC.
    Most brokers (including Exness) follow this schedule.

    Args:
        utc_time: UTC datetime. Uses current UTC time if None.

    Returns:
        True if market is closed for weekend.
    """
    if utc_time is None:
        utc_time = datetime.now(timezone.utc)

    weekday = utc_time.weekday()  # 0=Monday, 4=Friday, 5=Saturday, 6=Sunday
    hour = utc_time.hour

    # Saturday — all day closed
    if weekday == 5:
        return True

    # Sunday before 22:00 UTC — still closed
    if weekday == 6 and hour < 22:
        return True

    # Friday after 22:00 UTC — market closing
    if weekday == 4 and hour >= 22:
        return True

    return False


def get_weekend_liquidation_phase(utc_time: Optional[datetime] = None, liquidation_hour: int = 20) -> int:
    """
    Determine the weekend liquidation phase on Friday (UTC):
    - Phase 0: Normal trading (before liquidation_hour - 2)
    - Phase 1: Block new entries (between liquidation_hour - 2 and liquidation_hour - 0.5)
    - Phase 2: Cancel pending/DCA orders (between liquidation_hour - 0.5 and liquidation_hour)
    - Phase 3: Force close all positions (at/after liquidation_hour)
    """
    if utc_time is None:
        utc_time = datetime.now(timezone.utc)
    
    weekday = utc_time.weekday()  # 4 = Friday
    
    if weekday != 4:
        return 0
        
    hour = utc_time.hour
    minute = utc_time.minute
    time_float = hour + minute / 60.0
    
    if time_float >= liquidation_hour:
        return 3
    elif time_float >= (liquidation_hour - 0.5):
        return 2
    elif time_float >= (liquidation_hour - 2.0):
        return 1
        
    return 0


def is_market_closing_soon(utc_time: Optional[datetime] = None, close_hour_utc: int = 21) -> bool:
    """
    Check if it's Friday approaching market close — time to exit all positions
    to avoid Weekend Gap risk.

    Forex market closes Friday ~22:00 UTC. This function triggers early
    (default: Friday 21:00 UTC) to allow orderly position closure while
    liquidity is still reasonable.

    Args:
        utc_time: UTC datetime. Uses current UTC time if None.
        close_hour_utc: Hour (UTC) on Friday after which positions should be closed.
                        Default 21 = 1 hour before market close.

    Returns:
        True if it's Friday at or after close_hour_utc (but before full weekend).
    """
    if utc_time is None:
        utc_time = datetime.now(timezone.utc)

    weekday = utc_time.weekday()  # 4 = Friday
    hour = utc_time.hour

    # Friday at or after the configured close hour, but before 22:00 (full weekend)
    if weekday == 4 and close_hour_utc <= hour < 22:
        return True

    return False


def is_trading_hours(utc_time: Optional[datetime] = None) -> bool:
    """
    Check if current time is within any trading session.
    Also checks for weekend market closure.

    Args:
        utc_time: UTC datetime. Uses current UTC time if None.

    Returns:
        True if within trading hours (any session, not weekend).
    """
    if utc_time is None:
        utc_time = datetime.now(timezone.utc)

    # Weekend check first
    if is_weekend(utc_time):
        return False

    session = get_current_session(utc_time)
    return session != Session.OFF


def get_session_name(utc_time: Optional[datetime] = None) -> str:
    """Get session name as string for logging."""
    return get_current_session(utc_time).value

