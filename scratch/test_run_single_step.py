import sys
import os
import traceback

sys.path.insert(0, os.path.abspath("."))

def test_step():
    try:
        from v9_continuum.main import V9ContinuumBot, Session
        bot = V9ContinuumBot()
        print("Bot initialized successfully.")
        bot.connector.connect()
        print("MT5 connected.")
        bot.recover_active_cycles()
        print(f"Recovered cycles: {list(bot.active_cycles.keys())}")
        bot.manage_cycles()
        print("manage_cycles() passed.")
        bot.process_signals(Session.ASIA)
        print("process_signals() passed.")
    except Exception as e:
        print(f"ERROR CAUGHT: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_step()
