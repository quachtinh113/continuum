"""
NowTrading 2.1 — Backtest Runner
CLI entry point to download data and run backtests.
"""

import argparse
from datetime import datetime, timezone, timedelta
import sys
from pathlib import Path

from config import settings
from config.symbols import get_all_symbols
from src.data_downloader import HistoricalDataDownloader
from src.backtest_engine import BacktestEngine, VirtualPortfolio
from src.audit_logger import log_info, log_error


def parse_args():
    parser = argparse.ArgumentParser(description="NowTrading 2.1 Backtesting Tool")
    
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download fresh historical data from MT5 before running backtest",
    )
    
    parser.add_argument(
        "--start-date",
        type=str,
        default=(datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d"),
        help="Start date for backtest (YYYY-MM-DD), default: 90 days ago",
    )
    
    parser.add_argument(
        "--end-date",
        type=str,
        default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        help="End date for backtest (YYYY-MM-DD), default: today",
    )
    
    parser.add_argument(
        "--symbols",
        type=str,
        default="all",
        help="Comma-separated symbols to backtest (e.g. 'EURUSD,GBPUSD,XAUUSD') or 'all'",
    )
    
    parser.add_argument(
        "--balance",
        type=float,
        default=10000.0,
        help="Initial simulation account balance (USD), default: 10000.0",
    )
    
    parser.add_argument(
        "--report",
        action="store_true",
        help="Save a detailed markdown report of the backtest under logs/ directory",
    )
    
    parser.add_argument(
        "--no-time-stop",
        action="store_true",
        help="Disable 12H review and 24H force close time-based exits in backtest",
    )

    return parser.parse_args()


def run():
    args = parse_args()

    # Parse dates
    try:
        start_dt = datetime.strptime(args.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        # End date should cover the full end day (23:59:59)
        end_dt = datetime.strptime(args.end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
    except ValueError as e:
        log_error(f"Invalid date format: {e}. Use YYYY-MM-DD.")
        sys.exit(1)

    # Parse symbols
    if args.symbols.lower() == "all":
        symbols = get_all_symbols()
    else:
        symbols = [s.strip().upper() for s in args.symbols.split(",")]
        # Verify valid symbols
        valid_symbols = get_all_symbols()
        invalid = [s for s in symbols if s not in valid_symbols]
        if invalid:
            log_error(f"Invalid symbols requested: {invalid}. Available: {valid_symbols}")
            sys.exit(1)

    # 1. Download data if requested
    if args.download:
        log_info("Initializing MT5 Connection to download historical data...")
        downloader = HistoricalDataDownloader()
        
        # We need a slightly wider start date for indicators to warm up (e.g., need 50 bars prior to start date)
        # 50 H4 bars is ~8 days, so we add 15 days margin for download
        download_start = start_dt - timedelta(days=15)
        
        timeframes = ["M15", "H1", "H4"]
        log_info(f"Downloading history for {len(symbols)} symbols...")
        success = downloader.download_portfolio(symbols, timeframes, download_start, end_dt)
        log_info(f"Finished downloading history. Successfully saved {success} files.")

    # 2. Run Backtest
    log_info(f"Starting backtest simulation from {args.start_date} to {args.end_date}...")
    log_info(f"Symbols: {symbols} │ Initial Balance: ${args.balance:,.2f}")
    
    engine = BacktestEngine()
    try:
        portfolio, metrics = engine.run_backtest(
            symbols, start_dt, end_dt, initial_balance=args.balance, no_time_stop=args.no_time_stop
        )
    except Exception as e:
        log_error(f"Backtest failed to run: {e}")
        sys.exit(1)

    # 3. Print Console Report
    print_cli_report(metrics)

    # 4. Save Markdown Report if requested
    if args.report:
        save_markdown_report(args, metrics, portfolio, symbols)


def print_cli_report(m: dict):
    """Print backtest metrics to the console in a clean format."""
    print("\n" + "=" * 60)
    print("                 NOWTRADING 2.1 BACKTEST SUMMARY")
    print("=" * 60)
    print(f" Backtest Period  : {m.get('total_cycles', 0)} completed cycles simulated")
    print("-" * 60)
    print(f" Initial Balance  : ${m.get('initial_balance'):,.2f}")
    print(f" Final Balance    : ${m.get('final_balance'):,.2f}")
    print(f" Net Profit       : ${m.get('total_profit_usd'):+,.2f} ({m.get('profit_percent'):+,.2f}%)")
    print("-" * 60)
    print(f" Win Rate         : {m.get('win_rate'):.2f}%")
    print(f" Gross Profit     : ${m.get('gross_profit'):,.2f}")
    print(f" Gross Loss       : ${m.get('gross_loss'):,.2f}")
    print(f" Profit Factor    : {m.get('profit_factor')}")
    print(f" Max Drawdown     : ${m.get('max_drawdown_usd'):,.2f} ({m.get('max_drawdown_percent'):.2f}%)")
    print("-" * 60)
    print(f" Avg Cycle Length : {m.get('avg_holding_hours')} hours")
    print(f" Avg DCA Layers   : {m.get('avg_dca_layers')}")
    print(f" Max DCA Reached  : {m.get('max_dca_reached')} / 3")
    print("-" * 60)
    print(" Close Reasons Breakdown:")
    for reason, count in m.get("reasons", {}).items():
        print(f"   - {reason:<20}: {count} ({count/m.get('total_cycles')*100:.1f}%)")
    print("=" * 60 + "\n")


def save_markdown_report(args, m: dict, p: VirtualPortfolio, symbols: list):
    """Save a detailed markdown report of the backtest under logs/ directory."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = settings.PROJECT_ROOT / "logs" / f"backtest_report_{timestamp}.md"
    
    # Render reasons breakdown
    reasons_table = "| Reason | Count | Percentage |\n| :--- | :--- | :--- |\n"
    for reason, count in m.get("reasons", {}).items():
        reasons_table += f"| {reason} | {count} | {count/m.get('total_cycles')*100:.1f}% |\n"
        
    # Render trade history table (up to latest 100 trades to keep file readable)
    trades_table = "| Time | Symbol | Direction | Entry Px | Exit Px | DCA | Holding | Net P&L | Reason |\n"
    trades_table += "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
    
    for c in reversed(p.closed_cycles[-100:]):
        trades_table += (
            f"| {c.entry_time.strftime('%m-%d %H:%M')} | {c.symbol} | {c.direction} | "
            f"{c.base_entry_price:.5f} | {c.average_entry_price:.5f} | {c.num_dca_layers} | "
            f"{c.holding_hours:.1f}h | {c.current_profit_usd:+.2f} USD | {c.close_reason} |\n"
        )

    content = f"""# NowTrading 2.1 Backtest Report

Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")} UTC

## Simulation Settings
* **Start Date**: {args.start_date}
* **End Date**: {args.end_date}
* **Symbols Evaluated**: `{symbols}`
* **Initial Balance**: ${args.balance:,.2f}

## Performance Summary
| Metric | Value |
| :--- | :--- |
| **Initial Balance** | ${m.get('initial_balance'):,.2f} |
| **Final Balance** | ${m.get('final_balance'):,.2f} |
| **Net Profit** | **${m.get('total_profit_usd'):+,.2f} ({m.get('profit_percent'):+,.2f}%)** |
| **Win Rate** | {m.get('win_rate'):.2f}% |
| **Gross Profit** | ${m.get('gross_profit'):,.2f} |
| **Gross Loss** | ${m.get('gross_loss'):,.2f} |
| **Profit Factor** | {m.get('profit_factor')} |
| **Max Drawdown (Equity)** | ${m.get('max_drawdown_usd'):,.2f} ({m.get('max_drawdown_percent'):.2f}%) |
| **Avg Cycle Length** | {m.get('avg_holding_hours')} hours |
| **Avg DCA Layers** | {m.get('avg_dca_layers')} |
| **Max DCA Layers Reached** | {m.get('max_dca_reached')} / 3 |

## Close Reasons
{reasons_table}

## Last 100 Closed Cycles
{trades_table}
"""

    report_file.write_text(content, encoding="utf-8")
    log_info(f"Detailed report saved successfully to {report_file.relative_to(settings.PROJECT_ROOT)}")


if __name__ == "__main__":
    run()
