#include "v9/core/types.hpp"
#include "v9/config/symbols.hpp"
#include "v9/config/settings.hpp"
#include "v9/layers/indicators.hpp"
#include "v9/layers/position_sizer.hpp"
#include "v9/layers/kalman.hpp"
#include "v9/layers/smc.hpp"
#include "v9/core/governor.hpp"
#include "v9/ml/ml_gatekeeper.hpp"
#include "v9/execution/cycle_manager.hpp"
#include "v9/backtest/backtest_engine.hpp"
#include "v9/backtest/monte_carlo.hpp"

#include <iostream>
#include <iomanip>
#include <cassert>
#include <cmath>

using namespace v9;

int total_tests = 0;
int passed_tests = 0;

#define TEST_ASSERT(condition, msg) \
    do { \
        total_tests++; \
        if (condition) { \
            passed_tests++; \
            std::cout << "  [PASS] " << msg << std::endl; \
        } else { \
            std::cerr << "  [FAIL] " << msg << " (Line " << __LINE__ << ")" << std::endl; \
        } \
    } while (0)

void run_position_sizer_unit_tests() {
    std::cout << "\n========================================================" << std::endl;
    std::cout << "   RUNNING C++ POSITION SIZER UNIT TEST SUITE (12 TESTS)" << std::endl;
    std::cout << "========================================================" << std::endl;

    PositionSizer sizer;

    // Test 1: Standard EURUSD Major Sizing ($10,000 Equity, ATR=0.0010, Multiplier=1.5 -> SL=15 pips -> Budget=$50 -> Lot=0.33)
    {
        double lot = sizer.calculate_lot_size(10000.0, 0.0010, "EURUSD", 0.5, 0.5, 1.0850, {}, 1.5);
        TEST_ASSERT(lot == 0.33, "Test 1: EURUSD Major Sizing standard ($10,000 equity, 0.5% risk -> 0.33 lot)");
    }

    // Test 2: Standard GBPUSD Major Sizing ($5,000 Equity, ATR=0.0015, Multiplier=1.5 -> SL=22.5 pips -> Budget=$25 -> Lot=0.11)
    {
        double lot = sizer.calculate_lot_size(5000.0, 0.0015, "GBPUSD", 0.5, 0.5, 1.2700, {}, 1.5);
        TEST_ASSERT(lot == 0.11, "Test 2: GBPUSD Major Sizing standard ($5,000 equity, 0.5% risk -> 0.11 lot)");
    }

    // Test 3: Standard USDJPY Cross Sizing ($10,000, ATR=0.30, Multiplier=1.5, Px=155.0 -> Budget=$50 -> Lot=0.17)
    {
        double lot = sizer.calculate_lot_size(10000.0, 0.30, "USDJPY", 0.5, 0.5, 155.0, {}, 1.5);
        TEST_ASSERT(lot == 0.17, "Test 3: USDJPY Cross Sizing with 1.0/price quote conversion -> 0.17 lot");
    }

    // Test 4: Standard USDCAD Cross Sizing ($10,000, ATR=0.0015, Multiplier=1.5, Px=1.38 -> Budget=$50 -> Lot=0.30)
    {
        double lot = sizer.calculate_lot_size(10000.0, 0.0015, "USDCAD", 0.5, 0.5, 1.38, {}, 1.5);
        TEST_ASSERT(lot == 0.30, "Test 4: USDCAD Cross Sizing -> 0.30 lot");
    }

    // Test 5: Gold XAUUSD Sizing ($10,000, ATR=8.00, Multiplier=1.5 -> SL=$12.00 -> Budget=$50 -> Lot=0.04)
    {
        double lot = sizer.calculate_lot_size(10000.0, 8.00, "XAUUSD", 0.5, 0.5, 2350.0, {}, 1.5);
        TEST_ASSERT(lot == 0.04, "Test 5: Gold XAUUSD Sizing standard ($100/point contract -> 0.04 lot)");
    }

    // Test 6: High Volatility Gold Sizing ($10,000, ATR=20.00, Multiplier=4.0 -> SL=$80.00 -> Budget=$50 -> Lot Raw=0.006 -> Rejected 0.0)
    {
        double lot = sizer.calculate_lot_size(10000.0, 20.00, "XAUUSD", 0.5, 0.5, 2350.0, {}, 4.0);
        TEST_ASSERT(lot == 0.0, "Test 6: High Volatility Gold Sizing rejected (0.0 lot) by Quantization Guard");
    }

    // Test 7: Index US100 Sizing ($10,000, ATR=50.0, Multiplier=1.5 -> SL=75 pts -> Budget=$50 -> Lot=0.66)
    {
        double lot = sizer.calculate_lot_size(10000.0, 50.0, "US100", 0.5, 0.5, 18500.0, {}, 1.5);
        TEST_ASSERT(lot == 0.66, "Test 7: US100 Index Sizing (1 unit contract size -> 0.66 lot)");
    }

    // Test 8: Index US30 Sizing ($10,000, ATR=150.0, Multiplier=1.5 -> SL=225 pts -> Budget=$50 -> Lot=0.22)
    {
        double lot = sizer.calculate_lot_size(10000.0, 150.0, "US30", 0.5, 0.5, 39000.0, {}, 1.5);
        TEST_ASSERT(lot == 0.22, "Test 8: US30 Index Sizing (1 unit contract size -> 0.22 lot)");
    }

    // Test 9: Micro-Account Quantization Guard REJECTION ($200 Account, Gold ATR=12.0, Multiplier=4.0 -> Risk at 0.01 is $48.0 > Budget $1.05 -> Return 0.0)
    {
        double lot = sizer.calculate_lot_size(200.0, 12.0, "XAUUSD", 0.5, 0.5, 2350.0, {}, 4.0);
        TEST_ASSERT(lot == 0.0, "Test 9: Micro-Account Guard REJECTS Gold entry when min lot exceeds 105% budget");
    }

    // Test 10: Micro-Account Small FX Entry ($800 Account, EURUSD ATR=0.0010, Multiplier=4.0 -> Risk at 0.01 is $4.00 == Budget $4.00 -> Lot=0.01)
    {
        double lot = sizer.calculate_lot_size(800.0, 0.0010, "EURUSD", 0.5, 0.5, 1.0850, {}, 4.0);
        TEST_ASSERT(lot == 0.01, "Test 10: Micro-Account accepts exact budget fit -> 0.01 lot");
    }

    // Test 11: Correlation Haircut (Open EURUSD, Sizing GBPUSD -> 30% reduction: 0.11 * 0.7 = 0.07 lot)
    {
        double lot = sizer.calculate_lot_size(5000.0, 0.0015, "GBPUSD", 0.5, 0.5, 1.2700, {"EURUSD"}, 1.5);
        TEST_ASSERT(lot == 0.07, "Test 11: Correlation Haircut applied to same FX asset class -> 0.07 lot");
    }

    // Test 12: Zero/Negative Equity Edge Case
    {
        double lot = sizer.calculate_lot_size(0.0, 0.0015, "EURUSD", 0.5);
        TEST_ASSERT(lot == 0.0, "Test 12: Zero equity safety check returns 0.0 lot");
    }
}

void run_indicator_unit_tests() {
    std::cout << "\n========================================================" << std::endl;
    std::cout << "   RUNNING C++ TECHNICAL INDICATOR UNIT TESTS" << std::endl;
    std::cout << "========================================================" << std::endl;

    std::vector<double> prices = {
        100.0, 102.0, 101.5, 103.0, 104.5, 103.5, 105.0, 106.5, 106.0, 107.5,
        108.0, 107.0, 109.0, 110.5, 111.0, 110.0, 112.5, 113.0, 112.0, 114.5
    };

    auto rsi = TechnicalIndicators::calculate_rsi(prices, 14);
    TEST_ASSERT(!rsi.empty() && rsi.back() > 50.0 && rsi.back() < 100.0, "Test: RSI calculation valid within (50, 100) for uptrend");

    double er = TechnicalIndicators::calculate_efficiency_ratio(prices, 10);
    TEST_ASSERT(er > 0.0 && er <= 1.0, "Test: Efficiency Ratio bounded in (0, 1]");

    KalmanFilterTracker kalman(1e-4, 1e-2);
    double smoothed = 0.0;
    for (double p : prices) {
        smoothed = kalman.update(p);
    }
    TEST_ASSERT(smoothed > 100.0 && smoothed < 120.0, "Test: Kalman Filter converges to price equilibrium");
}

void run_governor_unit_tests() {
    std::cout << "\n========================================================" << std::endl;
    std::cout << "   RUNNING C++ PORTFOLIO GOVERNOR UNIT TESTS" << std::endl;
    std::cout << "========================================================" << std::endl;

    PortfolioGovernor gov;
    std::vector<ActiveCycle> cycles;

    // Test: Clean initial state
    RiskDecision d1 = gov.evaluate_risk_matrix("EURUSD", cycles, 10000.0, 10000.0, 1000);
    TEST_ASSERT(d1.approved, "Test: Governor approves EURUSD when portfolio is empty");

    // Test: USD Concentration Limit (2 max)
    ActiveCycle c1, c2;
    c1.symbol = "EURUSD";
    c2.symbol = "USDJPY";
    cycles.push_back(c1);
    cycles.push_back(c2);

    RiskDecision d2 = gov.evaluate_risk_matrix("USDCAD", cycles, 10000.0, 10000.0, 1000);
    TEST_ASSERT(!d2.approved && d2.status_code == "USD_CONCENTRATION", "Test: Governor blocks 3rd USD symbol (Concentration Guard)");

    // Test: Daily Drawdown Hard Stop (5%)
    RiskDecision d3 = gov.evaluate_risk_matrix("AUDUSD", {}, 9400.0, 10000.0, 1000); // 6% DD
    TEST_ASSERT(!d3.approved && d3.status_code == "DAILY_DD_BREACH", "Test: Governor locks system on Daily Drawdown >= 5%");
    TEST_ASSERT(gov.system_status == "LOCKED", "Test: System status set to LOCKED");

    // Test: Manual Unlock
    bool unlocked = gov.manual_unlock("AdminQuant", "Manual recovery audit passed");
    TEST_ASSERT(unlocked && gov.system_status == "OPERATIONAL", "Test: Institutional Manual Unlock restores OPERATIONAL status");
}

int main() {
    std::cout << "=================================================================" << std::endl;
    std::cout << "      CONTINUUM V9: MODERN C++ CORE ENGINE TEST RUNNER" << std::endl;
    std::cout << "=================================================================" << std::endl;

    run_position_sizer_unit_tests();
    run_indicator_unit_tests();
    run_governor_unit_tests();

    std::cout << "\n=================================================================" << std::endl;
    std::cout << "   UNIT TEST SUMMARY: " << passed_tests << "/" << total_tests << " TESTS PASSED (" 
              << (total_tests > 0 ? (passed_tests * 100 / total_tests) : 0) << "%)" << std::endl;
    std::cout << "=================================================================" << std::endl;

    // Test Backtest Engine simulation on 4 Core Assets
    std::cout << "\n[Running C++ High-Speed Backtest Simulation on 4 Core Assets]..." << std::endl;
    BacktestEngine bt_engine(10000.0, 0.5, 0.80);
    std::vector<std::string> core_symbols = {"XAUUSD", "USDJPY", "AUDUSD", "USDCAD"};

    auto res = bt_engine.run(core_symbols, "../data/historical", 0, 50000);
    const auto& trades = res.first;
    const auto& m = res.second;

    std::cout << "-----------------------------------------------------------------" << std::endl;
    std::cout << "  C++ Engine Executed  : " << m.total_trades << " trades" << std::endl;
    std::cout << "  Win Rate             : " << std::fixed << std::setprecision(2) << m.win_rate << "% (" << m.wins << "W / " << m.losses << "L)" << std::endl;
    std::cout << "  Net Realized Profit  : $" << std::setprecision(2) << m.net_profit << " (" << m.return_pct << "%)" << std::endl;
    std::cout << "  Profit Factor        : " << m.profit_factor << std::endl;
    std::cout << "  Max Drawdown         : " << m.max_drawdown_pct << "% ($" << m.max_drawdown_usd << ")" << std::endl;
    std::cout << "  Annualized Sharpe    : " << m.annualized_sharpe << std::endl;
    std::cout << "  Sortino Ratio        : " << m.sortino << std::endl;
    std::cout << "  Payoff Ratio         : " << m.payoff_ratio << "R" << std::endl;
    std::cout << "-----------------------------------------------------------------" << std::endl;

    if (!trades.empty()) {
        std::cout << "\n[Running C++ Monte Carlo 1,000-Path Bootstrap Survival Simulation]..." << std::endl;
        auto mc = MonteCarloSimulator::run_simulation(trades, 10000.0, 1000, 42);
        std::cout << "  Survival Rate at 10% DD Limit : " << mc.survival_rate_10dd << "%" << std::endl;
        std::cout << "  Survival Rate at 20% DD Limit : " << mc.survival_rate_20dd << "% (Near Zero-Ruin)" << std::endl;
        std::cout << "  Worst 95th Percentile DD      : " << mc.dd_95th << "%" << std::endl;
        std::cout << "  Median Simulated Capital      : $" << mc.median_final_equity << std::endl;
    }
    std::cout << "=================================================================\n" << std::endl;

    return (passed_tests == total_tests) ? 0 : 1;
}
