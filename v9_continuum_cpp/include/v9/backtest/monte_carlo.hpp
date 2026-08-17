#pragma once

#include "v9/core/types.hpp"
#include <vector>
#include <random>
#include <cmath>
#include <algorithm>
#include <numeric>

namespace v9 {

struct MonteCarloResult {
    int simulations{1000};
    double survival_rate_5dd{0.0};
    double survival_rate_10dd{0.0};
    double survival_rate_20dd{0.0};
    double dd_95th{0.0};
    double dd_99th{0.0};
    double median_final_equity{0.0};
    double worst_5th_equity{0.0};
};

class MonteCarloSimulator {
public:
    static MonteCarloResult run_simulation(
        const std::vector<TradeRecord>& trades,
        double initial_capital = 10000.0,
        int n_simulations = 1000,
        unsigned int seed = 42
    ) {
        MonteCarloResult res;
        res.simulations = n_simulations;

        if (trades.empty()) return res;

        std::vector<double> pnls;
        pnls.reserve(trades.size());
        for (const auto& t : trades) {
            pnls.push_back(t.final_pnl);
        }

        std::mt19937 rng(seed);
        std::uniform_int_distribution<size_t> dist(0, pnls.size() - 1);

        std::vector<double> max_drawdowns;
        std::vector<double> final_equities;
        max_drawdowns.reserve(n_simulations);
        final_equities.reserve(n_simulations);

        int ruin_5 = 0;
        int ruin_10 = 0;
        int ruin_20 = 0;

        for (int s = 0; s < n_simulations; ++s) {
            double current_eq = initial_capital;
            double peak_eq = initial_capital;
            double max_dd_pct = 0.0;

            for (size_t i = 0; i < pnls.size(); ++i) {
                size_t rand_idx = dist(rng);
                current_eq += pnls[rand_idx];
                if (current_eq > peak_eq) {
                    peak_eq = current_eq;
                }
                double dd = (peak_eq - current_eq) / peak_eq * 100.0;
                if (dd > max_dd_pct) {
                    max_dd_pct = dd;
                }
            }

            max_drawdowns.push_back(max_dd_pct);
            final_equities.push_back(current_eq);

            if (max_dd_pct >= 5.0) ruin_5++;
            if (max_dd_pct >= 10.0) ruin_10++;
            if (max_dd_pct >= 20.0) ruin_20++;
        }

        std::sort(max_drawdowns.begin(), max_drawdowns.end());
        std::sort(final_equities.begin(), final_equities.end());

        res.survival_rate_5dd = (1.0 - static_cast<double>(ruin_5) / n_simulations) * 100.0;
        res.survival_rate_10dd = (1.0 - static_cast<double>(ruin_10) / n_simulations) * 100.0;
        res.survival_rate_20dd = (1.0 - static_cast<double>(ruin_20) / n_simulations) * 100.0;

        size_t idx_95 = static_cast<size_t>(n_simulations * 0.95);
        size_t idx_99 = static_cast<size_t>(n_simulations * 0.99);
        size_t idx_50 = static_cast<size_t>(n_simulations * 0.50);
        size_t idx_5 = static_cast<size_t>(n_simulations * 0.05);

        res.dd_95th = max_drawdowns[std::min(idx_95, max_drawdowns.size() - 1)];
        res.dd_99th = max_drawdowns[std::min(idx_99, max_drawdowns.size() - 1)];
        res.median_final_equity = final_equities[std::min(idx_50, final_equities.size() - 1)];
        res.worst_5th_equity = final_equities[std::min(idx_5, final_equities.size() - 1)];

        return res;
    }
};

} // namespace v9
