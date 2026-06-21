"""
NowTrading 2.1 — Account Auditor
Performs a live scan of the MetaTrader 5 account and validates risk constraints.
Run: python check_account.py
"""

import sys
import os
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings
from src.mt5_connector import MT5Connector


def print_title(title: str):
    print(f"\n============================================================")
    print(f"  {title}")
    print(f"============================================================")


def print_row(label: str, value: str, color_code: str = ""):
    label_formatted = f"  {label:<25} │"
    if color_code == "green":
        print(f"{label_formatted} \033[92m{value}\033[0m")
    elif color_code == "red":
        print(f"{label_formatted} \033[91m{value}\033[0m")
    elif color_code == "yellow":
        print(f"{label_formatted} \033[93m{value}\033[0m")
    elif color_code == "cyan":
        print(f"{label_formatted} \033[96m{value}\033[0m")
    else:
        print(f"{label_formatted} {value}")


def main():
    import sys
    if sys.version_info >= (3, 7):
        sys.stdout.reconfigure(encoding='utf-8')

    connector = MT5Connector()

    print_title("NowTrading 2.1 — Account Risk Audit")
    print_row("Scan Time (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    # Connect to MT5
    if not connector.connect():
        print_row("MT5 Status", "FAILED TO CONNECT", "red")
        sys.exit(1)

    try:
        import MetaTrader5 as mt5

        # Get Account Info
        info = mt5.account_info()
        if not info:
            print_row("Account Info", "FAILED TO RETRIEVE", "red")
            sys.exit(1)

        # Get Positions
        positions = mt5.positions_get()
        open_count = len(positions) if positions is not None else 0

        # Calculations
        floating_profit = info.profit
        margin_level = (info.equity / info.margin * 100) if info.margin > 0 else 0

        # Print Details
        print_title("1. Account Metrics")
        print_row("Account Number", str(info.login), "cyan")
        print_row("Account Owner", info.name)
        print_row("Server", info.server)
        print_row("Trading Mode", "Demo" if info.trade_mode == 0 else "Real", "yellow")
        print_row("Leverage", f"1:{info.leverage}")
        print_row("Currency", info.currency)

        print_title("2. Financial Status")
        print_row("Balance", f"${info.balance:,.2f}")
        print_row("Equity", f"${info.equity:,.2f}")
        print_row("Margin Used", f"${info.margin:,.2f}")
        print_row("Free Margin", f"${info.margin_free:,.2f}")

        # Margin level check
        if margin_level == 0:
            print_row("Margin Level", "N/A (No open trades)")
        elif margin_level < 200:
            print_row("Margin Level", f"{margin_level:.2f}% (CRITICAL)", "red")
        elif margin_level < 500:
            print_row("Margin Level", f"{margin_level:.2f}% (Warning)", "yellow")
        else:
            print_row("Margin Level", f"{margin_level:.2f}% (Healthy)", "green")

        print_title("3. Open Positions")
        print_row("Active Trade Count", str(open_count))
        print_row("Floating Profit/Loss", f"${floating_profit:+.2f}", "green" if floating_profit >= 0 else "red")

        if open_count > 0 and positions:
            print("\n  Details:")
            print(f"  {'Ticket':<10} │ {'Symbol':<12} │ {'Type':<6} │ {'Volume':<6} │ {'Open Price':<10} │ {'Profit PnL':<10}")
            print(f"  {'-'*11}┼{'-'*14}┼{'-'*8}┼{'-'*8}┼{'-'*12}┼{'-'*11}")
            for pos in positions:
                p_type = "BUY" if pos.type == 0 else "SELL"
                p_color = "\033[92m" if pos.profit >= 0 else "\033[91m"
                print(
                    f"  {pos.ticket:<10} │ {pos.symbol:<12} │ {p_type:<6} │ {pos.volume:<6.2f} │ "
                    f"{pos.price_open:<10.5f} │ {p_color}${pos.profit:+.2f}\033[0m"
                )

        # 4. Risk Pre-Trade Validations
        print_title("4. Pre-Trade Risk Verification")

        risk_passed = True
        warnings = []

        # Check Drawdown
        max_dd = settings.MAX_DAILY_DRAWDOWN_USD
        floating_loss = abs(floating_profit) if floating_profit < 0 else 0.0
        if floating_loss >= max_dd:
            warnings.append(f"Floating loss (${floating_loss:.2f}) exceeds Max Drawdown (${max_dd:.2f})")
            risk_passed = False
            print_row("Daily Drawdown Check", "EXCEEDED", "red")
        else:
            print_row("Daily Drawdown Check", "PASSED", "green")

        # Check Active Cycles Exposure
        max_cycles = settings.MAX_ACTIVE_CYCLES
        if open_count >= max_cycles:
            warnings.append(f"Open trades ({open_count}) reaches Max Active Cycles ({max_cycles})")
            risk_passed = False
            print_row("Portfolio Limit Check", "FULL", "red")
        else:
            print_row("Portfolio Limit Check", "PASSED", "green")

        # Check Margin Free Safety
        if info.margin_free < 100.0:  # arbitrary buffer
            warnings.append(f"Free margin (${info.margin_free:.2f}) is low (< $100)")
            print_row("Free Margin Buffer", "LOW BUFFER", "yellow")
        else:
            print_row("Free Margin Buffer", "PASSED", "green")

        # Check Live Mode
        if settings.LIVE_TRADING:
            print_row("Execution Target", "LIVE MARKET DEAL", "red")
        else:
            print_row("Execution Target", "DRY RUN (Paper Trade)", "green")

        print_title("5. Audit Verdict")
        if risk_passed:
            print_row("Verdict", "QUALIFIED FOR ENTRIES", "green")
            print("  Bot is fully ready to place new deals when signal triggers.")
        else:
            print_row("Verdict", "ENTRIES BLOCKED", "red")
            print("  Reason(s):")
            for w in warnings:
                print(f"    ⚠️  {w}")

    finally:
        connector.disconnect()
        print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
