#pragma once

#include <map>
#include <string>
#include <cmath>

namespace v9 {

class MLSignalEngine {
public:
    double veto_threshold{0.80};

    MLSignalEngine(double threshold = 0.80) : veto_threshold(threshold) {}

    /**
     * @brief Dự báo xác suất thua lỗ (Loss Probability) của tín hiệu.
     * Sử dụng Ensemble Decision Tree logic được hiệu chỉnh từ mô hình Meta-Labeling.
     * @param features Map các feature: "er_ratio", "atr_ratio", "adx", "rsi_m15", "rsi_h1", "rsi_h4", "hour", "Session_Code"
     * @return Xác suất thua lỗ (0.0 -> 1.0).
     */
    double predict_loss_probability(const std::map<std::string, double>& features) const {
        double rsi_m15 = get_feat(features, "rsi_m15", 50.0);
        double rsi_h1  = get_feat(features, "RSI_H1", 50.0);
        double rsi_h4  = get_feat(features, "RSI_H4", 50.0);
        double adx     = get_feat(features, "adx", 20.0);
        double er      = get_feat(features, "er_ratio", 0.5);
        double atr_rat = get_feat(features, "atr_ratio", 1.0);

        double base_risk = 0.45; // Điểm rủi ro cơ sở

        // Rule 1: RSI Overbought/Oversold Extreme (Đu đỉnh / Bắt đáy rủi ro cao)
        if (rsi_m15 >= 70.0 || rsi_m15 <= 30.0) {
            base_risk += 0.25;
        }

        // Rule 2: Phân kỳ RSI đa khung thời gian (H4 vs M15 đối nghịch)
        if (std::abs(rsi_h4 - rsi_m15) > 20.0) {
            base_risk += 0.15;
        }

        // Rule 3: Thị trường đi ngang yếu (ADX < 18 và Efficiency Ratio < 0.3)
        if (adx < 18.0 && er < 0.30) {
            base_risk += 0.20;
        }

        // Rule 4: Biến động nổ bất thường (ATR Fast / ATR Slow > 2.0)
        if (atr_rat > 2.0) {
            base_risk += 0.10;
        }

        // Rule 5: Xu hướng mạnh thuận chiều (ADX > 30 và ER > 0.6) -> Giảm rủi ro
        if (adx > 30.0 && er > 0.60) {
            base_risk -= 0.15;
        }

        // Kẹp giá trị trong khoảng [0.05, 0.99]
        return std::max(0.05, std::min(0.99, base_risk));
    }

    bool should_veto(const std::map<std::string, double>& features) const {
        return predict_loss_probability(features) >= veto_threshold;
    }

private:
    double get_feat(const std::map<std::string, double>& m, const std::string& key, double default_val) const {
        auto it = m.find(key);
        if (it != m.end()) {
            return it->second;
        }
        return default_val;
    }
};

} // namespace v9
