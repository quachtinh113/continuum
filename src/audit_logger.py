"""
NowTrading 2.1 — Audit Logger
Logs every trading decision with full indicator context and severity levels.
Constitution §20: "No log = invalid decision."
Constitution §21: Audit Severity (INFO, WARNING, CRITICAL, FATAL)
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any, Dict

from config import settings


# ── Module-level logger ─────────────────────────────────────
_logger = logging.getLogger("NowTrading")
_initialized = False


def _init_logger():
    """Initialize logger with console + file handlers."""
    global _initialized
    if _initialized:
        return

    _logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))

    # Reconfigure streams to support UTF-8 on Windows command prompts
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    # Console handler — human-readable
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(
        "%(asctime)s │ %(levelname)-5s │ %(message)s",
        datefmt="%H:%M:%S"
    ))
    _logger.addHandler(console)

    _initialized = True


def _get_audit_file() -> Path:
    """Get today's audit log file path."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return settings.LOG_PATH / f"audit_{today}.jsonl"


def log_decision(
    symbol: str,
    session: str,
    indicators: Dict[str, Any],
    signal: str,
    risk_decision: Any,  # RiskDecision type
    execution_action: str,
) -> dict:
    """
    Log a trading decision (BUY/SELL/HOLD/VETO).
    Constitution §20, §21: Must log severity and all data. No log = invalid.
    """
    _init_logger()

    rsi_h4 = indicators.get("RSI_H4")
    rsi_h1 = indicators.get("RSI_H1")
    rsi_m15 = indicators.get("RSI_M15")
    adx = indicators.get("ADX")
    atr = indicators.get("ATR")
    
    severity = getattr(risk_decision, "severity", "INFO")
    status_str = getattr(risk_decision, "status_str", str(risk_decision))
    reason = getattr(risk_decision, "reason", "")

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "severity": severity,
        "symbol": symbol,
        "session": session,
        "RSI_H4": round(rsi_h4, 2) if rsi_h4 is not None else None,
        "RSI_H1": round(rsi_h1, 2) if rsi_h1 is not None else None,
        "RSI_M15": round(rsi_m15, 2) if rsi_m15 is not None else None,
        "ADX": round(adx, 2) if adx is not None else None,
        "ATR": round(atr, 6) if atr is not None else None,
        "signal": signal,
        "risk_decision": status_str,
        "execution_action": execution_action,
        "reason": reason,
    }

    # Write to JSONL file
    audit_file = _get_audit_file()
    with open(audit_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Console log
    emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}.get(signal, "⚫")
    risk_emoji = "✅" if status_str == "APPROVED" else "🚫"

    _logger.info(
        f"{emoji} {symbol:<8} │ {session:<10} │ "
        f"RSI: H4={_fmt(rsi_h4)} H1={_fmt(rsi_h1)} M15={_fmt(rsi_m15)} │ "
        f"ADX={_fmt(adx)} ATR={_fmt(atr, 5)} │ "
        f"{signal:<4} │ {risk_emoji} {status_str} [{severity}] │ "
        f"{execution_action} │ {reason}"
    )

    return entry


def log_cycle_event(
    event: str,
    symbol: str,
    direction: str,
    details: dict,
) -> dict:
    """
    Log a trade cycle event (open, close, DCA, etc.).
    """
    _init_logger()

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "symbol": symbol,
        "direction": direction,
        **details,
    }

    audit_file = _get_audit_file()
    with open(audit_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    _logger.info(
        f"📋 {event:<15} │ {symbol:<8} │ {direction} │ "
        f"{json.dumps(details, default=str)}"
    )

    return entry


def log_error(message: str, **context):
    """Log an error with optional context."""
    _init_logger()
    _logger.error(f"❌ {message} │ {context}" if context else f"❌ {message}")

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "ERROR",
        "severity": "WARNING",
        "message": message,
        **context,
    }
    audit_file = _get_audit_file()
    with open(audit_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def log_info(message: str):
    """Log an informational message."""
    _init_logger()
    _logger.info(f"ℹ️  {message}")


def _fmt(value: Optional[float], decimals: int = 2) -> str:
    """Format a float for display, handling None."""
    if value is None:
        return "N/A  "
    return f"{value:.{decimals}f}"
