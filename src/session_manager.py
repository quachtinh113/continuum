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

