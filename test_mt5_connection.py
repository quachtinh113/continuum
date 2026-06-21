"""
NowTrading 2.1 — MT5 Connection Test
Tests connection, account info, data retrieval, and indicator computation.
Run: python test_mt5_connection.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timezone


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_ok(msg: str):
    print(f"  ✅ {msg}")


def print_fail(msg: str):
    print(f"  ❌ {msg}")


def print_info(msg: str):
    print(f"  ℹ️  {msg}")


def main():
    print_header("NowTrading 2.1 — MT5 Connection Test")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    errors = []

    # ── Step 1: Import MetaTrader5 ──
    print_header("Step 1: Import MetaTrader5 Package")
    try:
        import MetaTrader5 as mt5
        print_ok(f"MetaTrader5 package imported (version: {mt5.__version__})")
    except ImportError:
        print_fail("MetaTrader5 not installed! Run: pip install MetaTrader5")
        sys.exit(1)

    # ── Step 2: Initialize MT5 ──
    print_header("Step 2: Initialize MT5 Terminal")
    from config import settings

    print_info(f"MT5 Path: {settings.MT5_PATH}")
    print_info(f"Account: {settings.MT5_ACCOUNT}")
    print_info(f"Server: {settings.MT5_SERVER}")
    print_info(f"Live Trading: {settings.LIVE_TRADING}")

    if not mt5.initialize(path=settings.MT5_PATH):
        error = mt5.last_error()
        print_fail(f"MT5 initialize failed: {error}")
        print_info("Make sure MetaTrader 5 terminal is installed and the path is correct.")
        print_info("Try updating MT5_PATH in .env file.")

        # Try without path
        print_info("Trying initialize without path...")
        if not mt5.initialize():
            print_fail(f"Still failed: {mt5.last_error()}")
            errors.append("MT5 initialize failed")
        else:
            print_ok("MT5 initialized (auto-detected path)")
    else:
        print_ok("MT5 terminal initialized")

    if errors:
        print_header("RESULT: Connection Failed")
        for e in errors:
            print_fail(e)
        mt5.shutdown()
        return

    # ── Step 3: Login ──
    print_header("Step 3: Login to Account")

    authorized = mt5.login(
        login=settings.MT5_ACCOUNT,
        password=settings.MT5_PASSWORD,
        server=settings.MT5_SERVER,
    )

    if not authorized:
        error = mt5.last_error()
        print_fail(f"Login failed: {error}")
        errors.append("Login failed")
        mt5.shutdown()
        print_header("RESULT: Login Failed")
        for e in errors:
            print_fail(e)
        return
    else:
        print_ok("Login successful!")

    # ── Step 4: Account Info ──
    print_header("Step 4: Account Information")

    account = mt5.account_info()
    if account:
        print_ok(f"Account: {account.login}")
        print_ok(f"Name: {account.name}")
        print_ok(f"Server: {account.server}")
        print_ok(f"Balance: ${account.balance:.2f}")
        print_ok(f"Equity: ${account.equity:.2f}")
        print_ok(f"Margin: ${account.margin:.2f}")
        print_ok(f"Free Margin: ${account.margin_free:.2f}")
        print_ok(f"Leverage: 1:{account.leverage}")
        print_ok(f"Currency: {account.currency}")
        print_ok(f"Trade Mode: {'Demo' if account.trade_mode == 0 else 'Contest' if account.trade_mode == 1 else 'Real'}")
    else:
        print_fail("Cannot get account info")
        errors.append("Account info failed")

    # ── Step 5: Symbol Availability ──
    print_header("Step 5: Check Symbol Availability")

    from config.symbols import SYMBOLS, get_mt5_name

    available = []
    not_found = []

    for key, spec in SYMBOLS.items():
        mt5_name = spec.name
        info = mt5.symbol_info(mt5_name)
        if info is not None:
            # Make sure symbol is visible
            if not info.visible:
                mt5.symbol_select(mt5_name, True)
            tick = mt5.symbol_info_tick(mt5_name)
            if tick:
                spread = (tick.ask - tick.bid) / spec.pip_size
                print_ok(f"{key:<10} ({mt5_name:<12}) │ Bid: {tick.bid:<12.5f} Ask: {tick.ask:<12.5f} │ Spread: {spread:.1f} pips")
                available.append(key)
            else:
                print_info(f"{key:<10} ({mt5_name:<12}) │ Symbol exists but no tick data")
                not_found.append(key)
        else:
            print_fail(f"{key:<10} ({mt5_name:<12}) │ NOT FOUND on server")
            not_found.append(key)

    print_info(f"\nAvailable: {len(available)}/{len(SYMBOLS)}")
    if not_found:
        print_info(f"Not found: {not_found}")
        print_info("You may need to adjust MT5 symbol names in config/symbols.py")

    # ── Step 6: Data Retrieval Test ──
    print_header("Step 6: Data Retrieval (Candle Data)")

    test_symbol = available[0] if available else None
    if test_symbol:
        mt5_sym = get_mt5_name(test_symbol)

        for tf_name, tf_const in [("M15", mt5.TIMEFRAME_M15), ("H1", mt5.TIMEFRAME_H1), ("H4", mt5.TIMEFRAME_H4)]:
            rates = mt5.copy_rates_from_pos(mt5_sym, tf_const, 0, 50)
            if rates is not None and len(rates) > 0:
                import pandas as pd
                df = pd.DataFrame(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')
                latest = df.iloc[-1]
                print_ok(
                    f"{test_symbol} {tf_name:<3} │ "
                    f"{len(rates)} bars │ "
                    f"Latest: {latest['time']} │ "
                    f"O={latest['open']:.5f} H={latest['high']:.5f} "
                    f"L={latest['low']:.5f} C={latest['close']:.5f}"
                )
            else:
                print_fail(f"{test_symbol} {tf_name} │ No data: {mt5.last_error()}")
                errors.append(f"No data for {test_symbol} {tf_name}")
    else:
        print_fail("No available symbols to test data retrieval")
        errors.append("No symbols available")

    # ── Step 7: Indicator Computation Test ──
    print_header("Step 7: Indicator Computation")

    if test_symbol and not errors:
        try:
            import pandas_ta as ta
            mt5_sym = get_mt5_name(test_symbol)

            # Get H1 data
            rates = mt5.copy_rates_from_pos(mt5_sym, mt5.TIMEFRAME_H1, 0, 50)
            df = pd.DataFrame(rates)

            rsi = ta.rsi(df['close'], length=14)
            adx_df = ta.adx(high=df['high'], low=df['low'], close=df['close'], length=14)
            atr = ta.atr(high=df['high'], low=df['low'], close=df['close'], length=14)

            rsi_val = rsi.iloc[-1] if rsi is not None else None
            adx_val = adx_df['ADX_14'].iloc[-1] if adx_df is not None else None
            atr_val = atr.iloc[-1] if atr is not None else None

            print_ok(f"{test_symbol} H1 RSI(14): {rsi_val:.2f}")
            print_ok(f"{test_symbol} H1 ADX(14): {adx_val:.2f}")
            print_ok(f"{test_symbol} H1 ATR(14): {atr_val:.6f}")

            # Quick signal evaluation
            from src.signal_engine import SignalEngine
            from src.regime_engine import RegimeEngine
            engine = SignalEngine(RegimeEngine())

            # Get M15 and H4 RSI too
            rates_m15 = mt5.copy_rates_from_pos(mt5_sym, mt5.TIMEFRAME_M15, 0, 50)
            rates_h4 = mt5.copy_rates_from_pos(mt5_sym, mt5.TIMEFRAME_H4, 0, 50)

            df_m15 = pd.DataFrame(rates_m15)
            df_h4 = pd.DataFrame(rates_h4)

            rsi_m15 = ta.rsi(df_m15['close'], length=14).iloc[-1]
            rsi_h4 = ta.rsi(df_h4['close'], length=14).iloc[-1]

            indicators = {
                "RSI_H4": float(rsi_h4),
                "RSI_H1": float(rsi_val),
                "RSI_M15": float(rsi_m15),
                "ADX": float(adx_val),
                "ATR": float(atr_val),
            }

            signal = engine.evaluate(indicators)

            print_info(f"\n  📊 Live Signal for {test_symbol}:")
            print_info(f"     RSI H4={rsi_h4:.2f}  H1={rsi_val:.2f}  M15={rsi_m15:.2f}")
            print_info(f"     ADX={adx_val:.2f}  ATR={atr_val:.6f}")

            emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}.get(signal.value, "⚫")
            print_info(f"     Signal: {emoji} {signal.value}")
            print_info(f"     Reason: {engine.get_signal_reason(signal, indicators)}")

        except Exception as e:
            print_fail(f"Indicator computation error: {e}")
            errors.append(f"Indicator error: {e}")

    # ── Final Result ──
    print_header("FINAL RESULT")

    if not errors:
        print_ok("ALL TESTS PASSED! ✅")
        print_ok(f"Available symbols: {len(available)}/{len(SYMBOLS)}")
        print_ok("MT5 connection is working correctly.")
        print_info("\nReady for DRY_RUN mode!")
        print_info("Run: python -m src.main")
    else:
        print_fail(f"SOME TESTS FAILED ({len(errors)} errors):")
        for e in errors:
            print_fail(f"  • {e}")

    mt5.shutdown()
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
