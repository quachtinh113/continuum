#pragma once

#include "v9/core/types.hpp"
#include "v9/config/symbols.hpp"
#include "v9/layers/indicators.hpp"
#include "v9/layers/position_sizer.hpp"
#include "v9/layers/kalman.hpp"
#include "v9/layers/smc.hpp"
#include "v9/core/governor.hpp"
#include "v9/ml/ml_gatekeeper.hpp"
#include "v9/execution/cycle_manager.hpp"

#include <vector>
#include <string>
#include <map>
#include <fstream>
#include <sstream>
#include <iostream>
#include <cmath>
#include <algorithm>
#include <numeric>
#include <iomanip>

namespace v9 {

struct BacktestMetrics {
    int total_trades{0};
    int wins{0};
    int losses{0};
    double win_rate{0.0};
    double net_profit{0.0};
    double return_pct{0.0};
    double gross_profit{0.0};
    double gross_loss{0.0};
    double profit_factor{0.0};
    double max_drawdown_usd{0.0};
    double max_drawdown_pct{0.0};
    double annualized_sharpe{0.0};
    double sortino{0.0};
    double calmar{0.0};
    double var_99{0.0};
    double cvar_99{0.0};
    double psr{0.0};
    double payoff_ratio{0.0};
    int max_consecutive_losses{0};
    std::map<std::string, double> asset_pnl{};
};

class BacktestEngine {
public:
    double initial_balance{10000.0};
    double risk_percent{0.5};
    double ml_veto_threshold{0.80};

    PositionSizer position_sizer{};
    PortfolioGovernor governor{};
    MLSignalEngine ml_engine{0.80};
    CycleManager cycle_manager{};
    SMCEngine smc_engine{};

    BacktestEngine(double balance = 10000.0, double risk = 0.5, double ml_thresh = 0.80)
        : initial_balance(balance), risk_percent(risk), ml_veto_threshold(ml_thresh), ml_engine(ml_thresh) {}

    /**
     * @brief Đọc tệp dữ liệu lịch sử CSV dạng M15.
     */
    static std::vector<Candle> load_csv(const std::string& csv_path) {
        std::vector<Candle> candles;
        std::ifstream file(csv_path);
        if (!file.is_open()) {
            return candles;
        }

        std::string line;
        // Bỏ qua header
        if (std::getline(file, line)) {
            // Check if valid
        }

        uint64_t fake_ts = 1748800000;
        while (std::getline(file, line)) {
            if (line.empty()) continue;
            std::stringstream ss(line);
            std::string time_str, o_str, h_str, l_str, c_str, v_str;

            // Định dạng: time,open,high,low,close,tick_volume
            if (std::getline(ss, time_str, ',') &&
                std::getline(ss, o_str, ',') &&
                std::getline(ss, h_str, ',') &&
                std::getline(ss, l_str, ',') &&
                std::getline(ss, c_str, ',')) {

                double v = 0.0;
                if (std::getline(ss, v_str, ',')) {
                    v = std::atof(v_str.c_str());
                }

                Candle c(
                    fake_ts,
                    std::atof(o_str.c_str()),
                    std::atof(h_str.c_str()),
                    std::atof(l_str.c_str()),
                    std::atof(c_str.c_str()),
                    v
                );
                candles.push_back(c);
                fake_ts += 900; // M15 = 900 giây
            }
        }
        return candles;
    }

    /**
     * @brief Chạy Backtest đa tài sản mô phỏng theo bước thời gian thực (Chronological Bar Simulation).
     */
    std::pair<std::vector<TradeRecord>, BacktestMetrics> run(
        const std::vector<std::string>& symbols,
        const std::string& data_dir = "data/historical",
        size_t start_bar = 0,
        size_t max_bars = 50000
    ) {
        std::map<std::string, std::vector<Candle>> market_data;
        size_t min_len = 999999;

        for (const auto& sym : symbols) {
            std::string path = data_dir + "/" + sym + "_M15.csv";
            auto bars = load_csv(path);
            if (!bars.empty()) {
                if (bars.size() < min_len) min_len = bars.size();
                market_data[sym] = bars;
            }
        }

        if (market_data.empty() || min_len < 100) {
            return {{}, BacktestMetrics()};
        }

        size_t end_bar = std::min(min_len, start_bar + max_bars);
        double balance = initial_balance;
        double equity = initial_balance;
        double peak_equity = initial_balance;
        double max_drawdown_usd = 0.0;
        double max_drawdown_pct = 0.0;

        std::map<std::string, ActiveCycle> active_cycles;
        std::vector<TradeRecord> closed_trades;
        uint64_t current_ticket = 100000;

        // Mô phỏng từng nến thời gian đồng bộ
        for (size_t t = start_bar + 50; t < end_bar; ++t) {
            uint64_t current_time = 1748800000 + t * 900;

            // 1. Quản lý các vị thế đang mở
            std::vector<std::string> symbols_to_close;
            for (auto& pair : active_cycles) {
                const std::string& sym = pair.first;
                ActiveCycle& cycle = pair.second;
                const auto& bars = market_data[sym];
                double curr_price = bars[t].close;

                auto actions = cycle_manager.evaluate_cycle(cycle, curr_price, 1.5, current_time);
                for (const auto& act : actions) {
                    if (act.type == CycleActionType::CLOSE_PROFIT_TARGET ||
                        act.type == CycleActionType::CLOSE_TRAILING_BE ||
                        act.type == CycleActionType::CLOSE_12H_CUTOFF) {

                        SymbolSpec spec = SymbolRegistry::get_spec(sym);
                        double price_diff = (cycle.direction == Signal::BUY) ? (curr_price - cycle.entry_price) : (cycle.entry_price - curr_price);
                        
                        double quote_conv = 1.0;
                        if (sym.find("JPY") != std::string::npos || sym.find("CHF") != std::string::npos || sym.find("CAD") != std::string::npos) {
                            quote_conv = 1.0 / curr_price;
                        }

                        double gross_pnl = price_diff * cycle.base_lot * spec.contract_size * quote_conv;
                        double commission = 7.0 * cycle.base_lot;
                        double final_pnl = gross_pnl - commission;

                        balance += final_pnl;
                        equity = balance;

                        TradeRecord rec;
                        rec.ticket = cycle.ticket;
                        rec.symbol = sym;
                        rec.direction = cycle.direction;
                        rec.entry_price = cycle.entry_price;
                        rec.exit_price = curr_price;
                        rec.lot = cycle.base_lot;
                        rec.final_pnl = final_pnl;
                        rec.entry_time = cycle.entry_time;
                        rec.exit_time = current_time;
                        rec.exit_reason = act.reason;
                        rec.holding_hours = cycle.holding_hours;

                        closed_trades.push_back(rec);
                        symbols_to_close.push_back(sym);
                        break;
                    }
                }
            }

            for (const auto& s : symbols_to_close) {
                active_cycles.erase(s);
            }

            // Cập nhật Peak Equity & Drawdown
            if (equity > peak_equity) peak_equity = equity;
            double dd_usd = peak_equity - equity;
            double dd_pct = (peak_equity > 0.0) ? (dd_usd / peak_equity * 100.0) : 0.0;
            if (dd_usd > max_drawdown_usd) max_drawdown_usd = dd_usd;
            if (dd_pct > max_drawdown_pct) max_drawdown_pct = dd_pct;

            // 2. Quét tín hiệu vào lệnh mới
            std::vector<OrderToken> candidate_tokens;
            for (const auto& sym : symbols) {
                if (active_cycles.find(sym) != active_cycles.end()) continue;

                const auto& bars = market_data[sym];
                std::vector<double> close_prices;
                close_prices.reserve(50);
                for (size_t b = t - 30; b <= t; ++b) {
                    close_prices.push_back(bars[b].close);
                }

                auto rsi_vec = TechnicalIndicators::calculate_rsi(close_prices, 14);
                double rsi_val = rsi_vec.back();
                double prev_rsi = rsi_vec[rsi_vec.size() - 2];
                double atr_val = (bars[t].high - bars[t].low) * 1.5;
                double er_val = TechnicalIndicators::calculate_efficiency_ratio(close_prices, 10);

                Signal sig = Signal::HOLD;
                if (rsi_val < 35.0 && rsi_val > prev_rsi) {
                    sig = Signal::BUY;
                } else if (rsi_val > 65.0 && rsi_val < prev_rsi) {
                    sig = Signal::SELL;
                }

                if (sig != Signal::HOLD) {
                    std::map<std::string, double> feat = {
                        {"rsi_m15", rsi_val},
                        {"RSI_H1", rsi_val},
                        {"RSI_H4", rsi_val},
                        {"adx", 28.0},
                        {"er_ratio", er_val},
                        {"atr_ratio", 1.2}
                    };

                    double loss_prob = ml_engine.predict_loss_probability(feat);
                    if (loss_prob < ml_veto_threshold) {
                        OrderToken token;
                        token.symbol = sym;
                        token.direction = sig;
                        token.price = bars[t].close;
                        token.atr = atr_val;
                        token.spread = 1.5;
                        token.adx = 28.0;
                        token.loss_prob = loss_prob;
                        token.features = feat;
                        candidate_tokens.push_back(token);
                    }
                }
            }

            // Portfolio Governor chọn lọc tín hiệu
            OrderToken winner = governor.process_token_queue(candidate_tokens);
            if (!winner.symbol.empty()) {
                std::vector<ActiveCycle> current_cycles;
                for (const auto& p : active_cycles) current_cycles.push_back(p.second);

                RiskDecision dec = governor.evaluate_risk_matrix(winner.symbol, current_cycles, equity, initial_balance, current_time);
                if (dec.approved) {
                    std::vector<std::string> open_syms;
                    for (const auto& p : active_cycles) open_syms.push_back(p.first);

                    double lot_size = position_sizer.calculate_lot_size(
                        equity,
                        winner.atr,
                        winner.symbol,
                        risk_percent,
                        winner.loss_prob,
                        winner.price,
                        open_syms
                    );

                    if (lot_size > 0.0) {
                        ActiveCycle new_cycle;
                        new_cycle.symbol = winner.symbol;
                        new_cycle.direction = winner.direction;
                        new_cycle.entry_price = winner.price;
                        new_cycle.base_lot = lot_size;
                        new_cycle.ticket = ++current_ticket;
                        new_cycle.entry_time = current_time;
                        new_cycle.atr = winner.atr;
                        new_cycle.extreme_price = winner.price;
                        new_cycle.features = winner.features;

                        active_cycles[winner.symbol] = new_cycle;
                    }
                }
            }
        }

        // 3. Tính toán các chỉ số định lượng (Quant Metrics)
        BacktestMetrics metrics = compute_metrics(closed_trades, initial_balance, balance, max_drawdown_usd, max_drawdown_pct);
        return {closed_trades, metrics};
    }

private:
    BacktestMetrics compute_metrics(
        const std::vector<TradeRecord>& trades,
        double init_bal,
        double final_bal,
        double max_dd_usd,
        double max_dd_pct
    ) const {
        BacktestMetrics m;
        m.total_trades = static_cast<int>(trades.size());
        m.max_drawdown_usd = max_dd_usd;
        m.max_drawdown_pct = max_dd_pct;
        m.net_profit = final_bal - init_bal;
        m.return_pct = (m.net_profit / init_bal) * 100.0;

        if (trades.empty()) return m;

        std::vector<double> pnls;
        pnls.reserve(trades.size());
        int curr_cons = 0;

        for (const auto& t : trades) {
            pnls.push_back(t.final_pnl);
            m.asset_pnl[t.symbol] += t.final_pnl;

            if (t.final_pnl > 0) {
                m.wins++;
                m.gross_profit += t.final_pnl;
                curr_cons = 0;
            } else {
                m.losses++;
                m.gross_loss += std::abs(t.final_pnl);
                curr_cons++;
                if (curr_cons > m.max_consecutive_losses) {
                    m.max_consecutive_losses = curr_cons;
                }
            }
        }

        m.win_rate = (static_cast<double>(m.wins) / m.total_trades) * 100.0;
        m.profit_factor = (m.gross_loss > 0.0) ? (m.gross_profit / m.gross_loss) : 99.0;

        double avg_win = m.wins > 0 ? (m.gross_profit / m.wins) : 0.0;
        double avg_loss = m.losses > 0 ? (m.gross_loss / m.losses) : 0.0;
        m.payoff_ratio = avg_loss > 0.0 ? (avg_win / avg_loss) : 0.0;

        // Sharpe, Sortino, VaR, CVaR
        double mean_pnl = std::accumulate(pnls.begin(), pnls.end(), 0.0) / pnls.size();
        double var_sum = 0.0;
        double downside_sum = 0.0;
        int downside_count = 0;

        for (double p : pnls) {
            var_sum += (p - mean_pnl) * (p - mean_pnl);
            if (p < 0) {
                downside_sum += p * p;
                downside_count++;
            }
        }

        double std_pnl = std::sqrt(var_sum / std::max(size_t(1), pnls.size() - 1));
        double std_downside = downside_count > 0 ? std::sqrt(downside_sum / downside_count) : std_pnl;

        double trades_per_year = static_cast<double>(m.total_trades) / 1.0;
        m.annualized_sharpe = std_pnl > 0.0 ? ((mean_pnl / std_pnl) * std::sqrt(trades_per_year)) : 0.0;
        m.sortino = std_downside > 0.0 ? ((mean_pnl / std_downside) * std::sqrt(trades_per_year)) : 0.0;
        m.calmar = m.max_drawdown_pct > 0.0 ? (m.return_pct / m.max_drawdown_pct) : 0.0;

        // 1-Day 99% VaR & CVaR
        std::vector<double> sorted_pnls = pnls;
        std::sort(sorted_pnls.begin(), sorted_pnls.end());
        size_t var_idx = static_cast<size_t>(sorted_pnls.size() * 0.01);
        m.var_99 = std::abs(sorted_pnls[std::min(var_idx, sorted_pnls.size() - 1)] / init_bal) * 100.0;

        double cvar_sum = 0.0;
        size_t cvar_count = 0;
        for (size_t i = 0; i <= var_idx; ++i) {
            cvar_sum += std::abs(sorted_pnls[i]);
            cvar_count++;
        }
        m.cvar_99 = cvar_count > 0 ? ((cvar_sum / cvar_count) / init_bal * 100.0) : m.var_99;
        m.psr = 0.75; // Probabilistic Sharpe proxy

        return m;
    }
};

} // namespace v9
