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
    std::cout << "     CONTINUUM V9 C++: SUPER-ELITE UNIVERSE (AFTER PRUNING EURUSD & USDCAD)               " << std::endl;
    std::cout << "==========================================================================================" << std::endl;

    BacktestEngine engine(10000.0, 0.5, 0.80);

    // 1. 8-Asset Universe
    std::vector<std::string> u8 = {"AUDUSD", "NZDUSD", "USDCAD", "USDJPY", "XAUUSD", "US30", "BTCUSD", "EURUSD"};
    auto res8 = engine.run(u8, "../data/historical", 0, 26000);
    const auto& m8 = res8.second;

    // 2. 6-Asset Super-Elite Universe (Pruned EURUSD and USDCAD)
    std::vector<std::string> u6 = {"AUDUSD", "NZDUSD", "USDJPY", "XAUUSD", "US30", "BTCUSD"};
    auto res6 = engine.run(u6, "../data/historical", 0, 26000);
    const auto& m6 = res6.second;

    std::cout << std::left << std::setw(32) << "Quant KPI Metric"
              << " | " << std::setw(22) << "Truoc Loai Bo (8 Assets)"
              << " | " << std::setw(25) << "Sau Loai Bo (6 Super-Elite)"
              << " | Muc Do Cai Thien" << std::endl;
    std::cout << "------------------------------------------------------------------------------------------------------------" << std::endl;

    std::cout << std::left << std::setw(32) << "Win Rate (Ty le thang)"
              << " | " << std::fixed << std::setprecision(1) << std::setw(6) << m8.win_rate << "%                "
              << " | " << std::setw(6) << m6.win_rate << "%                   "
              << " | +" << (m6.win_rate - m8.win_rate) << "%" << std::endl;

    std::cout << std::left << std::setw(32) << "Profit Factor (Lai/Lo)"
              << " | " << std::fixed << std::setprecision(2) << std::setw(6) << m8.profit_factor << "                 "
              << " | " << std::setw(6) << m6.profit_factor << "                    "
              << " | +" << (m6.profit_factor - m8.profit_factor) << std::endl;

    std::cout << std::left << std::setw(32) << "Annualized Sharpe"
              << " | " << std::fixed << std::setprecision(2) << std::setw(6) << m8.annualized_sharpe << "                 "
              << " | " << std::setw(6) << m6.annualized_sharpe << "                    "
              << " | +" << (m6.annualized_sharpe - m8.annualized_sharpe) << std::endl;

    std::cout << std::left << std::setw(32) << "Sortino Ratio (Downside)"
              << " | " << std::fixed << std::setprecision(2) << std::setw(6) << m8.sortino << "                 "
              << " | " << std::setw(6) << m6.sortino << "                    "
              << " | +" << (m6.sortino - m8.sortino) << std::endl;

    std::cout << std::left << std::setw(32) << "Max Drawdown (%)"
              << " | " << std::fixed << std::setprecision(2) << std::setw(6) << m8.max_drawdown_pct << "% ($" << m8.max_drawdown_usd << ")        "
              << " | " << std::setw(6) << m6.max_drawdown_pct << "% ($" << m6.max_drawdown_usd << ")           "
              << " | Giam " << (m8.max_drawdown_pct - m6.max_drawdown_pct) << "% DD" << std::endl;

    std::cout << "==========================================================================================\n" << std::endl;
    return 0;
}
