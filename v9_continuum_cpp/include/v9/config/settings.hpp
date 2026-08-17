#pragma once

#include <string>
#include <vector>

namespace v9 {

struct Settings {
    // Risk limits
    double risk_per_trade_percent{0.5}; // Fixed Fractional Risk 0.5%
    double max_daily_drawdown_usd{50.0};
    int max_active_cycles{5};
    double ml_veto_threshold{0.80};

    // Hard Stop Loss multipliers per asset class
    double sl_multiplier_fx{4.0};
    double sl_multiplier_gold{4.0};
    double sl_multiplier_index{4.0};
    double sl_multiplier_crypto{4.0};

    // DCA Parameters
    int max_dca_layers{3};
    double dca_layer_1_atr{2.0};
    double dca_layer_2_atr{3.0};
    double dca_layer_3_atr{4.0};

    // Indicator thresholds
    int rsi_period{14};
    int adx_period{14};
    int atr_period{14};
    double adx_trend_threshold{25.0};
    double adx_range_threshold{18.0};

    // Time Management
    double holding_reduce_hours{12.0}; // 12H ML Cutoff
    double holding_max_hours{24.0};

    // Active Core Portfolio Watchlist
    std::vector<std::string> active_symbols{"XAUUSD", "USDJPY", "AUDUSD", "USDCAD"};
};

} // namespace v9
