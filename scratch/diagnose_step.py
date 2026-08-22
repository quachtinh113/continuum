import sys
import os
import traceback

sys.path.insert(0, os.path.abspath("."))

from v9_continuum.main import V9ContinuumBot

def main():
    try:
        print("[1] Initializing bot...")
        bot = V9ContinuumBot()
        print("[2] Connecting to MT5...")
        if not bot.connector.connect():
            print("MT5 connect failed!")
            return
        print("[3] Updating daily balance...")
        acc = bot.connector.get_account_info()
        bot.update_daily_balance(acc["balance"] if acc else 10000.0)
        print("[4] Recovering active cycles...")
        bot.recover_active_cycles()
        print(f"Active cycles count: {len(bot.active_cycles)}")
        for sym, c in bot.active_cycles.items():
            print(f"  Cycle {sym}: entry_time={c.get('entry_time')}, base_lot={c.get('base_lot')}, entry_price={c.get('entry_price')}")
        
        print("[5] Executing manage_cycles()...")
        bot.manage_cycles()
        print("[6] manage_cycles() executed successfully!")

        print("[7] Getting current session...")
        from src.session_manager import get_current_session
        from datetime import datetime, timezone
        now_utc = datetime.now(timezone.utc)
        session = get_current_session(now_utc)
        print(f"Current session: {session}")

        print("[8] Executing process_signals()...")
        bot.process_signals(session)
        print("[9] process_signals() executed successfully!")
        
    except BaseException as e:
        print(f"\n[EXCEPTION CAUGHT]: {type(e)}: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
