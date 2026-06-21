"""
NowTrading 2.1 — Historical Data Downloader
Downloads historical candle data from MetaTrader 5 and saves it to CSV files.
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

import pandas as pd

from config import settings
from config.symbols import get_all_symbols, get_mt5_name
from src.mt5_connector import MT5Connector, TIMEFRAME_MAP, mt5, MT5_AVAILABLE
from src.audit_logger import log_info, log_error


class HistoricalDataDownloader:
    """Downloads historical rates from MT5 terminal and writes to CSV."""

    def __init__(self, connector: Optional[MT5Connector] = None):
        self.connector = connector or MT5Connector()
        self.output_dir = settings.PROJECT_ROOT / "data" / "historical"

    def download_symbol_timeframe(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[Path]:
        """
        Download historical rates for a single symbol and timeframe.

        Args:
            symbol: Symbol key (e.g. "EURUSD")
            timeframe: Timeframe key (e.g. "M15", "H1", "H4")
            start_date: Start datetime (UTC)
            end_date: End datetime (UTC)

        Returns:
            Path to the saved CSV file, or None if failed.
        """
        if not MT5_AVAILABLE:
            log_error("MetaTrader5 package is not available.")
            return None

        if not self.connector.is_connected:
            log_error("Downloader not connected to MT5.")
            return None

        mt5_symbol = get_mt5_name(symbol)
        tf_code = TIMEFRAME_MAP.get(timeframe)
        if tf_code is None:
            log_error(f"Unsupported timeframe: {timeframe}")
            return None

        # Ensure market watch is enabled for the symbol
        mt5.symbol_select(mt5_symbol, True)

        # Convert date to naive datetime in UTC (MT5 copy_rates_range accepts datetime objects)
        # Note: timezone-naive datetime is assumed to be in the local terminal timezone,
        # but the copy_rates_range handles datetime inputs appropriately.
        # We use naive UTC datetimes for consistency.
        dt_start = start_date.replace(tzinfo=None)
        dt_end = end_date.replace(tzinfo=None)

        log_info(
            f"Downloading {symbol} ({mt5_symbol}) {timeframe} "
            f"from {dt_start.strftime('%Y-%m-%d')} to {dt_end.strftime('%Y-%m-%d')}..."
        )

        rates = mt5.copy_rates_range(mt5_symbol, tf_code, dt_start, dt_end)

        if rates is None or len(rates) == 0:
            err = mt5.last_error()
            log_error(
                f"Failed to download {symbol} {timeframe}. MT5 error code: {err}"
            )
            return None

        # Convert to DataFrame
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        out_file = self.output_dir / f"{symbol}_{timeframe}.csv"

        # Save to CSV
        df.to_csv(out_file, index=False)
        log_info(f"Saved {len(df)} bars to {out_file.relative_to(settings.PROJECT_ROOT)}")

        return out_file

    def download_portfolio(
        self,
        symbols: List[str],
        timeframes: List[str],
        start_date: datetime,
        end_date: datetime,
    ) -> int:
        """
        Download historical data for a list of symbols and timeframes.

        Returns:
            Number of successfully downloaded files.
        """
        success_count = 0
        total_tasks = len(symbols) * len(timeframes)
        task_idx = 0

        # Ensure connector is connected
        was_connected = self.connector.is_connected
        if not was_connected:
            if not self.connector.connect():
                log_error("Failed to connect to MT5 for download.")
                return 0

        try:
            for symbol in symbols:
                for tf in timeframes:
                    task_idx += 1
                    log_info(f"Task [{task_idx}/{total_tasks}]:")
                    res = self.download_symbol_timeframe(symbol, tf, start_date, end_date)
                    if res:
                        success_count += 1
        finally:
            if not was_connected:
                self.connector.disconnect()

        return success_count


if __name__ == "__main__":
    # Quick standalone testing
    import sys
    from datetime import timedelta

    # Default to last 90 days
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=90)

    symbols = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
    timeframes = ["M15", "H1", "H4"]

    log_info("Starting standalone historical data downloader...")
    downloader = HistoricalDataDownloader()
    success = downloader.download_portfolio(symbols, timeframes, start, end)
    log_info(f"Successfully downloaded {success} files.")
