#pragma once

#include "v9/core/types.hpp"
#include <vector>
#include <cmath>
#include <numeric>
#include <algorithm>

namespace v9 {

class TechnicalIndicators {
public:
    /**
     * @brief Tính RSI (Relative Strength Index) theo phương pháp làm mượt của Wilder.
     */
    static std::vector<double> calculate_rsi(const std::vector<double>& prices, int period = 14) {
        if (prices.size() < static_cast<size_t>(period + 1)) {
            return std::vector<double>(prices.size(), 50.0);
        }

        std::vector<double> rsi(prices.size(), 50.0);
        std::vector<double> gains(prices.size(), 0.0);
        std::vector<double> losses(prices.size(), 0.0);

        for (size_t i = 1; i < prices.size(); ++i) {
            double change = prices[i] - prices[i - 1];
            if (change > 0.0) {
                gains[i] = change;
            } else {
                losses[i] = -change;
            }
        }

        // Tính trung bình ban đầu
        double avg_gain = 0.0;
        double avg_loss = 0.0;
        for (int i = 1; i <= period; ++i) {
            avg_gain += gains[i];
            avg_loss += losses[i];
        }
        avg_gain /= period;
        avg_loss /= period;

        if (avg_loss == 0.0) {
            rsi[period] = 100.0;
        } else {
            double rs = avg_gain / avg_loss;
            rsi[period] = 100.0 - (100.0 / (1.0 + rs));
        }

        // Wilder's Smoothing cho các nến tiếp theo
        for (size_t i = period + 1; i < prices.size(); ++i) {
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period;
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period;

            if (avg_loss == 0.0) {
                rsi[i] = 100.0;
            } else {
                double rs = avg_gain / avg_loss;
                rsi[i] = 100.0 - (100.0 / (1.0 + rs));
            }
        }

        return rsi;
    }

    /**
     * @brief Tính Average True Range (ATR).
     */
    static std::vector<double> calculate_atr(const std::vector<Candle>& candles, int period = 14) {
        if (candles.empty()) return {};
        if (candles.size() < static_cast<size_t>(period)) {
            return std::vector<double>(candles.size(), candles[0].high - candles[0].low);
        }

        std::vector<double> tr(candles.size(), 0.0);
        tr[0] = candles[0].high - candles[0].low;

        for (size_t i = 1; i < candles.size(); ++i) {
            double hl = candles[i].high - candles[i].low;
            double hc = std::abs(candles[i].high - candles[i - 1].close);
            double lc = std::abs(candles[i].low - candles[i - 1].close);
            tr[i] = std::max(hl, std::max(hc, lc));
        }

        std::vector<double> atr(candles.size(), 0.0);
        double initial_atr = 0.0;
        for (int i = 0; i < period; ++i) {
            initial_atr += tr[i];
        }
        initial_atr /= period;
        atr[period - 1] = initial_atr;

        for (size_t i = period; i < candles.size(); ++i) {
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period;
        }

        return atr;
    }

    /**
     * @brief Tính ADX (Average Directional Index).
     */
    static std::vector<double> calculate_adx(const std::vector<Candle>& candles, int period = 14) {
        if (candles.size() < static_cast<size_t>(period * 2)) {
            return std::vector<double>(candles.size(), 20.0);
        }

        size_t n = candles.size();
        std::vector<double> tr(n, 0.0);
        std::vector<double> plus_dm(n, 0.0);
        std::vector<double> minus_dm(n, 0.0);

        for (size_t i = 1; i < n; ++i) {
            double up_move = candles[i].high - candles[i - 1].high;
            double down_move = candles[i - 1].low - candles[i].low;

            if (up_move > down_move && up_move > 0.0) {
                plus_dm[i] = up_move;
            }
            if (down_move > up_move && down_move > 0.0) {
                minus_dm[i] = down_move;
            }

            double hl = candles[i].high - candles[i].low;
            double hc = std::abs(candles[i].high - candles[i - 1].close);
            double lc = std::abs(candles[i].low - candles[i - 1].close);
            tr[i] = std::max(hl, std::max(hc, lc));
        }

        // Wilder smoothed TR, +DM, -DM
        std::vector<double> smoothed_tr(n, 0.0);
        std::vector<double> smoothed_pdm(n, 0.0);
        std::vector<double> smoothed_mdm(n, 0.0);
        std::vector<double> dx(n, 0.0);
        std::vector<double> adx(n, 20.0);

        double sum_tr = 0.0, sum_pdm = 0.0, sum_mdm = 0.0;
        for (int i = 1; i <= period; ++i) {
            sum_tr += tr[i];
            sum_pdm += plus_dm[i];
            sum_mdm += minus_dm[i];
        }

        smoothed_tr[period] = sum_tr;
        smoothed_pdm[period] = sum_pdm;
        smoothed_mdm[period] = sum_mdm;

        for (size_t i = period + 1; i < n; ++i) {
            smoothed_tr[i] = smoothed_tr[i - 1] - (smoothed_tr[i - 1] / period) + tr[i];
            smoothed_pdm[i] = smoothed_pdm[i - 1] - (smoothed_pdm[i - 1] / period) + plus_dm[i];
            smoothed_mdm[i] = smoothed_mdm[i - 1] - (smoothed_mdm[i - 1] / period) + minus_dm[i];

            double pdi = smoothed_tr[i] > 0.0 ? (100.0 * smoothed_pdm[i] / smoothed_tr[i]) : 0.0;
            double mdi = smoothed_tr[i] > 0.0 ? (100.0 * smoothed_mdm[i] / smoothed_tr[i]) : 0.0;
            double diff = std::abs(pdi - mdi);
            double sum_di = pdi + mdi;
            dx[i] = sum_di > 0.0 ? (100.0 * diff / sum_di) : 0.0;
        }

        // Smooth DX to get ADX
        size_t adx_start = period * 2;
        if (n > adx_start) {
            double sum_dx = 0.0;
            for (size_t i = period + 1; i <= adx_start; ++i) {
                sum_dx += dx[i];
            }
            adx[adx_start] = sum_dx / period;

            for (size_t i = adx_start + 1; i < n; ++i) {
                adx[i] = ((adx[i - 1] * (period - 1)) + dx[i]) / period;
            }
        }

        return adx;
    }

    /**
     * @brief Kaufman Efficiency Ratio (ER).
     */
    static double calculate_efficiency_ratio(const std::vector<double>& prices, int period = 10) {
        if (prices.size() < static_cast<size_t>(period + 1)) return 0.5;

        double change = std::abs(prices.back() - prices[prices.size() - 1 - period]);
        double volatility = 0.0;

        for (size_t i = prices.size() - period; i < prices.size(); ++i) {
            volatility += std::abs(prices[i] - prices[i - 1]);
        }

        return volatility > 0.0 ? (change / volatility) : 0.5;
    }
};

} // namespace v9
