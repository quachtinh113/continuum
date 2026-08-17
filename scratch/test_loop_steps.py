import sys
import os
import traceback
from pathlib import Path

# Add root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def test_loop_steps():
    from v9_continuum.main import V9ContinuumBot
    from src.session_manager import get_current_session
    from datetime import datetime, timezone

    try:
        bot = V9ContinuumBot()
        print("Bot initialized successfully.")
        if not bot.connector.connect():
            print("Failed to connect MT5.")
            return
        
        now_utc = datetime.now(timezone.utc)
        session = get_current_session(now_utc)
        print(f"Current session: {session}")
        
        print("Testing recover_active_cycles()...")
        bot.recover_active_cycles()
        print(f"Active cycles: {bot.active_cycles}")
        
        print("Testing process_signals()...")
        bot.process_signals(session)
        print("process_signals() completed.")
        
        print("Testing manage_cycles()...")
        bot.manage_cycles()
        print("manage_cycles() completed.")

    except Exception as e:
        print(f"Caught Exception: {type(e).__name__}: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_loop_steps()
