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
#include <numeric>
#include <cmath>
#include <algorithm>

using namespace v9;

struct AssetForensicResult {
    std::string symbol;
    int total_trades{0};
    int wins{0};
    int losses{0};
    double win_rate{0.0};
    double gross_profit{0.0};
    double gross_loss{0.0};
    double profit_factor{0.0};
    double net_profit{0.0};
    double return_pct{0.0};
    double max_drawdown_pct{0.0};
    double max_drawdown_usd{0.0};
    double avg_trade_pnl{0.0};
    double payoff_ratio{0.0};
    double sharpe{0.0};
    int max_consecutive_losses{0};
    double risk_adjusted_score{0.0};
};

int main() {
    std::cout << "==========================================================================================" << std::endl;
    std::cout << "     CONTINUUM V9 C++: DEEP-DIVE ASSET FORENSICS & PRUNING QUANT AUDIT (18 MONTHS)        " << std::endl;
    std::cout << "==========================================================================================" << std::endl;
    std::cout << " Horizon              : 18 Months (~26,000 M15 Bars)" << std::endl;
    std::cout << " Frictions Included   : Real-world Spread + Commission ($7/lot) + Slippage + Swaps" << std::endl;
    std::cout << " Risk Management      : Fixed Fractional 0.5% + Toxic Hours Mask (21-23h UTC & Fri >=19h)" << std::endl;
    std::cout << "==========================================================================================\n" << std::endl;

    BacktestEngine engine(10000.0, 0.5, 0.80);

    std::vector<std::string> test_symbols = {
        "AUDUSD", "NZDUSD", "USDCAD", "USDJPY", "XAUUSD", "US30", "BTCUSD", "EURUSD"
    };

    std::vector<AssetForensicResult> results;

    for (const auto& sym : test_symbols) {
        std::vector<std::string> single = {sym};
        auto res = engine.run(single, "../data/historical", 0, 26000);
        const auto& trades = res.first;
        const auto& m = res.second;

        AssetForensicResult r;
        r.symbol = sym;
        r.total_trades = static_cast<int>(trades.size());

        if (r.total_trades == 0) continue;

        int curr_cons = 0;
        std::vector<double> pnls;

        for (const auto& t : trades) {
            pnls.push_back(t.final_pnl);
            r.net_profit += t.final_pnl;

            if (t.final_pnl > 0) {
                r.wins++;
                r.gross_profit += t.final_pnl;
                curr_cons = 0;
            } else {
                r.losses++;
                r.gross_loss += std::abs(t.final_pnl);
                curr_cons++;
                if (curr_cons > r.max_consecutive_losses) {
                    r.max_consecutive_losses = curr_cons;
                }
            }
        }

        r.win_rate = (static_cast<double>(r.wins) / r.total_trades) * 100.0;
        r.profit_factor = (r.gross_loss > 0.0) ? (r.gross_profit / r.gross_loss) : 99.0;
        r.return_pct = (r.net_profit / 10000.0) * 100.0;
        r.avg_trade_pnl = r.net_profit / r.total_trades;

        double avg_win = (r.wins > 0) ? (r.gross_profit / r.wins) : 0.0;
        double avg_loss = (r.losses > 0) ? (r.gross_loss / r.losses) : 0.0;
        r.payoff_ratio = (avg_loss > 0.0) ? (avg_win / avg_loss) : 0.0;

        // Drawdown
        double running_eq = 10000.0;
        double peak_eq = 10000.0;
        for (double p : pnls) {
            running_eq += p;
            if (running_eq > peak_eq) peak_eq = running_eq;
            double dd_u = peak_eq - running_eq;
            double dd_p = (peak_eq > 0.0) ? (dd_u / peak_eq * 100.0) : 0.0;
            if (dd_u > r.max_drawdown_usd) r.max_drawdown_usd = dd_u;
            if (dd_p > r.max_drawdown_pct) r.max_drawdown_pct = dd_p;
        }

        // Sharpe
        double mean_pnl = r.avg_trade_pnl;
        double sq_sum = 0.0;
        for (double p : pnls) sq_sum += (p - mean_pnl) * (p - mean_pnl);
        double std_pnl = (r.total_trades > 1) ? std::sqrt(sq_sum / (r.total_trades - 1)) : 1.0;
        double t_per_year = static_cast<double>(r.total_trades) / 1.5;
        r.sharpe = (std_pnl > 0.0) ? ((mean_pnl / std_pnl) * std::sqrt(t_per_year)) : 0.0;

        // Composite Quant Score: (Profit Factor * 0.4) + (Return% / MaxDD% * 0.4) + (PayoffRatio * 0.2)
        double calmar = (r.max_drawdown_pct > 0.0) ? (r.return_pct / r.max_drawdown_pct) : 0.0;
        r.risk_adjusted_score = (r.profit_factor * 0.35) + (calmar * 0.35) + (r.payoff_ratio * 0.30);

        results.push_back(r);
    }

    // Sort from highest score to lowest score
    std::sort(results.begin(), results.end(), [](const AssetForensicResult& a, const AssetForensicResult& b) {
        return a.risk_adjusted_score > b.risk_adjusted_score;
    });

    std::cout << "------------------------------------------------------------------------------------------------------------------------" << std::endl;
    std::cout << std::left << std::setw(6) << "Rank"
              << " | " << std::setw(8) << "Asset"
              << " | " << std::setw(8) << "Trades"
              << " | " << std::setw(8) << "WinRate"
              << " | " << std::setw(6) << "PF"
              << " | " << std::setw(12) << "Net PnL ($)"
              << " | " << std::setw(8) << "Max DD"
              << " | " << std::setw(6) << "Sharpe"
              << " | " << std::setw(7) << "Payoff"
              << " | " << std::setw(8) << "MaxLoss"
              << " | " << std::setw(7) << "Score"
              << " | Verdict / Recommendation" << std::endl;
    std::cout << "------------------------------------------------------------------------------------------------------------------------" << std::endl;

    int rank = 1;
    for (const auto& r : results) {
        std::string verdict;
        if (rank <= 4) {
            verdict = "🌟 TIER 1 (COT LOI - DUNG DAU)";
        } else if (rank <= 6) {
            verdict = "🟢 TIER 2 (TOT - GIU LAI)";
        } else {
            verdict = "⚠️ TIER 3 (YEU NHAT - NEN LOAI BO)";
        }

        std::cout << std::left << "#" << std::setw(5) << rank
                  << " | " << std::setw(8) << r.symbol
                  << " | " << std::right << std::setw(6) << r.total_trades << "  "
                  << " | " << std::setw(6) << std::fixed << std::setprecision(1) << r.win_rate << "%"
                  << " | " << std::setw(6) << std::setprecision(2) << r.profit_factor
                  << " | $" << std::setw(9) << std::setprecision(2) << r.net_profit << " "
                  << " | " << std::setw(6) << std::setprecision(2) << r.max_drawdown_pct << "%"
                  << " | " << std::setw(6) << std::setprecision(2) << r.sharpe
                  << " | " << std::setw(5) << std::setprecision(2) << r.payoff_ratio << "R"
                  << " | " << std::setw(4) << r.max_consecutive_losses << " lenh"
                  << " | " << std::setw(6) << std::setprecision(2) << r.risk_adjusted_score
                  << " | " << verdict << std::endl;
        rank++;
    }
    std::cout << "------------------------------------------------------------------------------------------------------------------------\n" << std::endl;

    return 0;
}
