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
#include <vector>
#include <string>
#include <map>
#include <chrono>

using namespace v9;

int main() {
    std::cout << "==========================================================================================" << std::endl;
    std::cout << "     CONTINUUM V9 C++: GOLD (XAUUSD) QUANT ALPHA OPTIMIZATION (18 MONTHS)                 " << std::endl;
    std::cout << "==========================================================================================" << std::endl;

    // Test 1: Baseline Gold (0.5% risk)
    BacktestEngine engine_base(10000.0, 0.5, 0.80);
    std::vector<std::string> gold_sym = {"XAUUSD"};
    auto res_base = engine_base.run(gold_sym, "../data/historical", 0, 26000);
    const auto& m_base = res_base.second;

    // Test 2: Gold Optimized Risk (0.8% risk - due to ultra-low 0.58% base DD)
    BacktestEngine engine_opt(10000.0, 0.8, 0.80);
    auto res_opt = engine_opt.run(gold_sym, "../data/historical", 0, 26000);
    const auto& m_opt = res_opt.second;

    // Test 3: Gold High Alpha Risk (1.0% risk - max institutional single-trade limit)
    BacktestEngine engine_high(10000.0, 1.0, 0.80);
    auto res_high = engine_high.run(gold_sym, "../data/historical", 0, 26000);
    const auto& m_high = res_high.second;

    std::cout << std::left << std::setw(32) << "Gold Sizing / Model"
              << " | " << std::setw(8) << "Trades"
              << " | " << std::setw(10) << "Win Rate"
              << " | " << std::setw(8) << "PF"
              << " | " << std::setw(14) << "Net PnL ($)"
              << " | " << std::setw(10) << "Max DD (%)"
              << " | Sharpe" << std::endl;
    std::cout << "------------------------------------------------------------------------------------------------------------" << std::endl;

    auto print_row = [](const std::string& name, const BacktestMetrics& m) {
        std::cout << std::left << std::setw(32) << name
                  << " | " << std::right << std::setw(6) << m.total_trades << "  "
                  << " | " << std::setw(6) << std::fixed << std::setprecision(1) << m.win_rate << "%    "
                  << " | " << std::setw(6) << std::setprecision(2) << m.profit_factor << " "
                  << " | $" << std::setw(9) << std::setprecision(2) << m.net_profit << "  "
                  << " | " << std::setw(6) << std::setprecision(2) << m.max_drawdown_pct << "%    "
                  << " | " << std::setw(5) << std::setprecision(2) << m.annualized_sharpe << std::endl;
    };

    print_row("1. Baseline Gold (0.5% Risk)", m_base);
    print_row("2. Optimized Gold (0.8% Risk)", m_opt);
    print_row("3. Alpha Boost Gold (1.0% Risk)", m_high);

    std::cout << "==========================================================================================\n" << std::endl;
    return 0;
}
