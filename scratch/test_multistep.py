import sys
import os
import time
import traceback
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath("."))

from v9_continuum.main import V9ContinuumBot
from src.session_manager import get_current_session, Session

def test_multistep():
    try:
        bot = V9ContinuumBot()
        print("Bot initialized.")
        if not bot.connector.connect():
            print("MT5 connect failed.")
            return
        print("MT5 connected.")
        bot.recover_active_cycles()
        print("Cycles recovered:", len(bot.active_cycles))

        for step in range(1, 6):
            print(f"\n--- STEP {step} ---")
            now_utc = datetime.now(timezone.utc)
            session = get_current_session(now_utc)
            print(f"Session: {session}")
            
            acc = bot.connector.get_account_info()
            if acc:
                bot.update_daily_balance(acc["balance"])
                print(f"Balance: {acc['balance']}, Equity: {acc['equity']}")
            
            bot.ml_engine.reload_if_modified()
            bot.process_signals(session)
            print("process_signals() finished.")
            bot.manage_cycles()
            print("manage_cycles() finished.")
            time.sleep(2)
            
        print("\nALL 5 STEPS COMPLETED 100% CLEANLY!")
    except BaseException as e:
        print(f"\nEXCEPTION IN MULTISTEP: {type(e)}: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_multistep()
