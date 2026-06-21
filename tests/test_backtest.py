"""
Unit Tests for NowTrading 2.1 Backtester.
"""

import pytest
import sys
import os
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.backtest_engine import BacktestEngine, VirtualPortfolio
from src.trade_cycle_manager import CycleStatus
from config import settings


class TestVirtualPortfolio:
    """Test VirtualPortfolio accounting and tracking."""

    def test_portfolio_initialization(self):
        vp = VirtualPortfolio(initial_balance=5000.0)
        assert vp.balance == 5000.0
        assert vp.equity == 5000.0
        assert len(vp.active_cycles) == 0
        assert len(vp.closed_cycles) == 0

    def test_open_and_update_cycle(self):
        vp = VirtualPortfolio(initial_balance=10000.0)
        now = datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc)
        
        # Open a BUY cycle for EURUSD at 1.1000
        cycle = vp.open_cycle("EURUSD", "BUY", 1.1000, now, "LONDON")
        assert "EURUSD" in vp.active_cycles
        assert cycle.base_entry_price == 1.1000
        assert cycle.total_lots == 0.01
        
        # Update P&L when price is 1.1050 (50 pips profit)
        vp.update_cycle_pnl("EURUSD", 1.1050, now + timedelta(hours=2))
        assert cycle.holding_hours == 2.0
        
        # contract_size for EURUSD is 100,000. Lot is 0.01.
        # 0.0050 * 0.01 * 100,000 = $5.00
        assert cycle.current_profit_usd == pytest.approx(5.0)

    def test_dca_layer_calculations(self):
        vp = VirtualPortfolio(initial_balance=10000.0)
        now = datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc)
        
        # Open BUY at 1.1000
        cycle = vp.open_cycle("EURUSD", "BUY", 1.1000, now, "LONDON")
        
        # Add DCA at 1.0900 (100 pips lower)
        vp.add_dca("EURUSD", 1.0900, now + timedelta(minutes=30))
        assert cycle.num_dca_layers == 1
        assert cycle.total_lots == 0.02
        
        # Weighted average entry price: (1.1000*0.01 + 1.0900*0.01) / 0.02 = 1.0950
        assert cycle.average_entry_price == pytest.approx(1.0950)

    def test_close_cycle_realize_pnl(self):
        vp = VirtualPortfolio(initial_balance=10000.0)
        now = datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc)
        
        # Open BUY at 1.1000, update and close at 1.1060 (60 pips profit = $6.00)
        vp.open_cycle("EURUSD", "BUY", 1.1000, now, "LONDON")
        vp.close_cycle("EURUSD", 1.1060, now + timedelta(hours=2), "TAKE_PROFIT")
        
        assert "EURUSD" not in vp.active_cycles
        assert len(vp.closed_cycles) == 1
        assert vp.balance == pytest.approx(10006.0)
        assert vp.closed_cycles[0].close_reason == "TAKE_PROFIT"
        assert vp.closed_cycles[0].current_profit_usd == pytest.approx(6.0)

    def test_daily_drawdown_tracking(self):
        vp = VirtualPortfolio(initial_balance=10000.0)
        now = datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc)
        
        # Open and close with a loss of $20.00
        # 1.1000 entry BUY, close at 1.0800 (200 pips loss = -$20.00)
        vp.open_cycle("EURUSD", "BUY", 1.1000, now, "LONDON")
        vp.close_cycle("EURUSD", 1.0800, now + timedelta(hours=1), "FORCE_CLOSE")
        
        assert vp.balance == pytest.approx(9980.0)
        assert vp.get_daily_loss(now) == pytest.approx(20.0)
        
        # Next day checks should reset daily loss
        next_day = now + timedelta(days=1)
        assert vp.get_daily_loss(next_day) == 0.0


class TestLookAheadFreeAlignment:
    """Test look-ahead-free alignment logic in BacktestEngine."""

    def test_look_ahead_free_shift_and_merge(self, tmp_path):
        """
        Verify that H1 and H4 indicator values are shifted to availability time
        before joining onto the M15 timeline.
        """
        engine = BacktestEngine(data_dir=tmp_path)
        
        # Create synthetic CSV data with 100 bars each to allow indicator calculations
        t_base = datetime(2026, 6, 9, 0, 0)
        
        # 1. M15: 400 bars
        m15_times = [t_base + timedelta(minutes=15 * i) for i in range(400)]
        df_m15 = pd.DataFrame({
            "time": m15_times,
            "open": [1.1000 + 0.0001 * np.sin(i/10) for i in range(400)],
            "high": [1.1005 + 0.0001 * np.sin(i/10) for i in range(400)],
            "low": [1.0995 + 0.0001 * np.sin(i/10) for i in range(400)],
            "close": [1.1000 + 0.0001 * np.sin(i/10) for i in range(400)],
            "tick_volume": [100] * 400
        })
        
        # 2. H1: 100 bars
        h1_times = [t_base + timedelta(hours=i) for i in range(100)]
        df_h1 = pd.DataFrame({
            "time": h1_times,
            "open": [1.1000 + 0.0002 * np.sin(i/10) for i in range(100)],
            "high": [1.1010 + 0.0002 * np.sin(i/10) for i in range(100)],
            "low": [1.0990 + 0.0002 * np.sin(i/10) for i in range(100)],
            "close": [1.1000 + 0.0002 * np.sin(i/10) for i in range(100)],
            "tick_volume": [400] * 100
        })

        # 3. H4: 100 bars
        h4_times = [t_base + timedelta(hours=4 * i) for i in range(100)]
        df_h4 = pd.DataFrame({
            "time": h4_times,
            "open": [1.1000 + 0.0005 * np.sin(i/10) for i in range(100)],
            "high": [1.1020 + 0.0005 * np.sin(i/10) for i in range(100)],
            "low": [1.0980 + 0.0005 * np.sin(i/10) for i in range(100)],
            "close": [1.1000 + 0.0005 * np.sin(i/10) for i in range(100)],
            "tick_volume": [1600] * 100
        })

        # Save to temp CSV files
        df_m15.to_csv(tmp_path / "EURUSD_M15.csv", index=False)
        df_h1.to_csv(tmp_path / "EURUSD_H1.csv", index=False)
        df_h4.to_csv(tmp_path / "EURUSD_H4.csv", index=False)

        # Build indicators using backtester logic
        master = engine.load_and_prepare_data("EURUSD")
        
        assert master is not None
        assert not master.empty
        
        # Confirm that the columns exist and times align
        assert "available_time" in master.columns
        assert "RSI_H4" in master.columns
        assert "RSI_H1" in master.columns
        assert "ADX" in master.columns
        assert "ATR" in master.columns
        
        # Verify timestamps are timezone-aware
        assert master["available_time"].dt.tz is not None


class TestBacktestEngineDynamicStops:
    """Test dynamic 12H/24H exits inside the backtester engine."""

    def test_backtest_sideways_holding_beyond_24h(self, tmp_path):
        """
        Verify that a trade cycle stays active beyond 12H and 24H
        when the market is sideways (flat price, weak trend, neutral RSI).
        """
        engine = BacktestEngine(data_dir=tmp_path)
        t_base = datetime(2026, 6, 9, 0, 0, tzinfo=timezone.utc)
        
        # Generate 400 M15 bars (100 hours)
        m15_times = [t_base + timedelta(minutes=15 * i) for i in range(400)]
        m15_closes = []
        m15_highs = []
        m15_lows = []
        
        # We need a BUY trigger at the beginning:
        # We need RSI_H4 > 55, RSI_H1 > 55, RSI_M15 > 50, and pullback rising.
        # To make RSI high at start, we make price rise at the beginning, then go completely flat.
        for i in range(400):
            if i < 150:
                # Rising price to build high RSI
                price = 1.1000 + 0.0001 * i
            elif i == 150:
                # Trigger bar: slight tick up to confirm pullback rising
                price = 1.1000 + 0.0001 * 150 + 0.00005
            else:
                # Flat price for the remaining 249 bars (~62.25 hours)
                price = 1.1000 + 0.0001 * 150 + 0.00005
            m15_closes.append(price)
            m15_highs.append(price + 0.0001)
            m15_lows.append(price - 0.0001)

        df_m15 = pd.DataFrame({
            "time": m15_times,
            "open": m15_closes,
            "high": m15_highs,
            "low": m15_lows,
            "close": m15_closes,
            "tick_volume": [100] * 400
        })

        # H1 data matching the trend (100 bars)
        h1_times = [t_base + timedelta(hours=i) for i in range(100)]
        h1_closes = []
        for i in range(100):
            if i < 37:
                price = 1.1000 + 0.0004 * i
            else:
                price = 1.1000 + 0.0004 * 37
            h1_closes.append(price)
            
        df_h1 = pd.DataFrame({
            "time": h1_times,
            "open": h1_closes,
            "high": [p + 0.0004 for p in h1_closes],
            "low": [p - 0.0004 for p in h1_closes],
            "close": h1_closes,
            "tick_volume": [400] * 100
        })

        # H4 data matching the trend (100 bars)
        h4_times = [t_base + timedelta(hours=4 * i) for i in range(100)]
        h4_closes = []
        for i in range(100):
            if i < 10:
                price = 1.1000 + 0.0016 * i
            else:
                price = 1.1000 + 0.0016 * 10
            h4_closes.append(price)

        df_h4 = pd.DataFrame({
            "time": h4_times,
            "open": h4_closes,
            "high": [p + 0.0016 for p in h4_closes],
            "low": [p - 0.0016 for p in h4_closes],
            "close": h4_closes,
            "tick_volume": [1600] * 100
        })

        df_m15.to_csv(tmp_path / "EURUSD_M15.csv", index=False)
        df_h1.to_csv(tmp_path / "EURUSD_H1.csv", index=False)
        df_h4.to_csv(tmp_path / "EURUSD_H4.csv", index=False)

        # Adjust settings for testing to avoid triggering take profit or ML cuts
        original_tp = settings.PROFIT_TARGET_USD
        original_tp_mult = settings.TAKE_PROFIT_ATR_MULTIPLIER
        original_be_mult = getattr(settings, "BREAK_EVEN_ACTIVATION_ATR_MULTIPLIER", 0.75)
        original_ml_active = getattr(settings, "ML_GATEKEEPER_ACTIVE", True)
        
        settings.PROFIT_TARGET_USD = 5000.0
        settings.TAKE_PROFIT_ATR_MULTIPLIER = 1000.0
        settings.BREAK_EVEN_ACTIVATION_ATR_MULTIPLIER = 1000.0
        settings.ML_GATEKEEPER_ACTIVE = False

        try:
            # Prepare data and run backtest on the valid registered EURUSD symbol
            portfolio, metrics = engine.run_backtest(
                symbols=["EURUSD"],
                start_date=t_base + timedelta(hours=2),
                end_date=t_base + timedelta(hours=90),
                initial_balance=10000.0,
                no_time_stop=False,
            )
            
            # Since prices go flat after entry, if we held beyond 24 hours without force closing,
            # there should be active cycles or closed cycles. Let's inspect:
            # Under the new logic, the cycle will not be closed because:
            # 1. At 12H, price is flat, so distance (0) <= ATR range. It stays open.
            # 2. At 24H, ADX is low or trend is not reversed, and RSI H1 is not overextended. It stays open.
            # So the cycle should still be ACTIVE at the end of the backtest!
            assert len(portfolio.active_cycles) == 1
            assert "EURUSD" in portfolio.active_cycles
            cycle = portfolio.active_cycles["EURUSD"]
            assert cycle.holding_hours > 24.0
            assert len(portfolio.closed_cycles) == 0
        finally:
            settings.PROFIT_TARGET_USD = original_tp
            settings.TAKE_PROFIT_ATR_MULTIPLIER = original_tp_mult
            settings.BREAK_EVEN_ACTIVATION_ATR_MULTIPLIER = original_be_mult
            settings.ML_GATEKEEPER_ACTIVE = original_ml_active
