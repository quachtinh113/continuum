import sys
import os
import traceback

sys.path.insert(0, os.path.abspath("."))

from v9_continuum.main import V9ContinuumBot

def debug_run():
    try:
        bot = V9ContinuumBot()
        print("Bot initialized.")
        bot.connector.connect()
        print("MT5 connected.")
        bot.recover_active_cycles()
        print("Active cycles:", bot.active_cycles)
        
        # Test 1 loop iteration
        now_utc = bot.get_current_session()
        print("Current session:", now_utc)
        bot.manage_cycles()
        print("manage_cycles passed.")
        bot.process_signals(now_utc)
        print("process_signals passed.")
    except BaseException as e:
        print(f"DEBUG CAUGHT EXCEPTION: {type(e)} - {e}")
        traceback.print_exc()

if __name__ == "__main__":
    debug_run()
