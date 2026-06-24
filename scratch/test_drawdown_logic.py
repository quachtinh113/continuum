import sys
import os
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from datetime import datetime, date, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import bot class
from v9_continuum.main import V9ContinuumBot

class TestDrawdownFix(unittest.TestCase):
    def setUp(self):
        # Prevent actual MT5 connection and file logs during tests
        with patch('v9_continuum.main.MT5Connector') as mock_conn:
            self.bot = V9ContinuumBot()
            # Mock connector
            self.bot.connector = MagicMock()
            self.bot.connector.get_account_info.return_value = {"balance": 10000.0, "equity": 10000.0}
            self.bot.connector.get_positions.return_value = []
            self.bot.connector._dry_run = True
            
            # Mock close_all_positions
            self.bot.close_all_positions = MagicMock()
            
    @patch('v9_continuum.main.log_error')
    @patch('v9_continuum.main.log_info')
    def test_drawdown_flow(self, mock_log_info, mock_log_error):
        # 1. Initialize starting balance
        self.bot.start_of_day_balance = 10000.0
        self.bot.last_balance_update_day = date(2026, 6, 23)
        self.bot.governor.system_status = "OPERATIONAL"
        
        # 2. First Breach: Simulate equity dropping to 9600 (4% drawdown, limit is 3.0%)
        self.bot.connector.get_account_info.return_value = {"balance": 10000.0, "equity": 9600.0}
        self.bot.manage_cycles()
        
        # Verify that close_all_positions was called ONCE, and status is set to LOCKED
        self.bot.close_all_positions.assert_called_once()
        self.assertEqual(self.bot.governor.system_status, "LOCKED")
        mock_log_error.assert_any_call("🚨 Drawdown Limit Breached (4.00%). Emergency closing all positions and locking system!")
        
        # Reset mock call counter
        self.bot.close_all_positions.reset_mock()
        mock_log_error.reset_mock()
        
        # 3. Second Tick: Simulate another check while still in locked state
        # The drawdown calculation will still be 4.00%
        self.bot.manage_cycles()
        
        # Verify that close_all_positions is NOT called again (preventing redundant close attempts and log spam)
        self.bot.close_all_positions.assert_not_called()
        mock_log_error.assert_not_called()
        
        # 4. Day Change: Simulate moving to the next day
        # Let's mock datetime to return June 24th
        mock_today = date(2026, 6, 24)
        with patch('v9_continuum.main.datetime') as mock_datetime:
            # Setup datetime mock behavior
            mock_datetime.now.return_value = datetime(2026, 6, 24, 8, 0, 0, tzinfo=timezone.utc)
            
            # Call update_daily_balance with the new balance (e.g. 9600 after realizing the loss)
            self.bot.update_daily_balance(9600.0)
            
            # Verify that the start of day balance is updated
            self.assertEqual(self.bot.start_of_day_balance, 9600.0)
            self.assertEqual(self.bot.last_balance_update_day, mock_today)
            
            # CRITICAL FIX CHECK: Verify governor system status is reset to OPERATIONAL
            self.assertEqual(self.bot.governor.system_status, "OPERATIONAL")
            
        print("[SUCCESS] ALL TESTS PASSED SUCCESSFULLY! The fixes work perfectly.")

if __name__ == "__main__":
    unittest.main()
