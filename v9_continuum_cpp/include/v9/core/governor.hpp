#pragma once

#include "v9/core/types.hpp"
#include "v9/config/symbols.hpp"
#include <string>
#include <vector>
#include <map>
#include <algorithm>

namespace v9 {

class PortfolioGovernor {
public:
    std::string system_status{"OPERATIONAL"}; // "OPERATIONAL", "LOCKED"
    std::string lock_reason{""};
    uint64_t locked_at{0};

    int max_usd_exposure{2};
    int max_gold_exposure{1};
    int max_index_exposure{1};

    PortfolioGovernor() = default;

    /**
     * @brief Mở khóa hệ thống thủ công theo chuẩn quản trị quỹ (Zero Auto-Unlock Policy).
     */
    bool manual_unlock(const std::string& admin_user, const std::string& reason) {
        if (admin_user.empty() || reason.empty()) {
            return false;
        }
        system_status = "OPERATIONAL";
        lock_reason = "";
        locked_at = 0;
        return true;
    }

    /**
     * @brief Đánh giá ma trận rủi ro tập trung trước khi cho phép vào lệnh mới.
     */
    RiskDecision evaluate_risk_matrix(
        const std::string& symbol,
        const std::vector<ActiveCycle>& active_cycles,
        double equity,
        double start_of_day_balance,
        uint64_t current_time
    ) {
        // 1. Kiểm tra trạng thái khóa hệ thống (System Kill Switch)
        if (system_status == "LOCKED") {
            return RiskDecision(false, "System is LOCKED: " + lock_reason, "KILL_SWITCH");
        }

        // 2. Kiểm tra sụt giảm vốn trong ngày (Daily Drawdown Limit)
        if (start_of_day_balance > 0.0) {
            double daily_drawdown_pct = 100.0 * (start_of_day_balance - equity) / start_of_day_balance;
            if (daily_drawdown_pct >= 5.0) { // 5% Hard Daily Stop
                system_status = "LOCKED";
                lock_reason = "Daily Drawdown Limit Breached (>= 5.0%)";
                locked_at = current_time;
                return RiskDecision(false, lock_reason, "DAILY_DD_BREACH");
            }
        }

        // 3. Đếm số lượng vị thế rủi ro theo nhóm tài sản
        int usd_count = 0;
        int gold_count = 0;
        int index_count = 0;

        for (const auto& cycle : active_cycles) {
            if (is_usd_symbol(cycle.symbol)) usd_count++;
            if (cycle.symbol == "XAUUSD") gold_count++;
            SymbolSpec spec = SymbolRegistry::get_spec(cycle.symbol);
            if (spec.category == "INDEX") index_count++;
        }

        // 4. Kiểm tra nồng độ rủi ro USD Factor
        if (is_usd_symbol(symbol) && usd_count >= max_usd_exposure) {
            return RiskDecision(false, "USD factor concentration exceeded limit (" + std::to_string(max_usd_exposure) + ")", "USD_CONCENTRATION");
        }

        // 5. Kiểm tra nồng độ rủi ro Vàng (Gold Factor)
        if (symbol == "XAUUSD" && gold_count >= max_gold_exposure) {
            return RiskDecision(false, "Gold exposure concentration exceeded limit", "GOLD_CONCENTRATION");
        }

        // 6. Kiểm tra nồng độ rủi ro Chỉ số chứng khoán (Index Factor)
        SymbolSpec target_spec = SymbolRegistry::get_spec(symbol);
        if (target_spec.category == "INDEX" && index_count >= max_index_exposure) {
            return RiskDecision(false, "Index exposure concentration exceeded limit", "INDEX_CONCENTRATION");
        }

        return RiskDecision(true, "Approved by Governor", "APPROVED");
    }

    /**
     * @brief Chọn lựa token tín hiệu có điểm ưu tiên cao nhất trong hàng đợi cạnh tranh.
     */
    OrderToken process_token_queue(const std::vector<OrderToken>& candidate_tokens) const {
        if (candidate_tokens.empty()) {
            return OrderToken();
        }

        // Sắp xếp ưu tiên: Điểm rủi ro ML thấp nhất (Loss Prob nhỏ nhất), sau đó là ADX cao nhất
        OrderToken best = candidate_tokens[0];
        for (size_t i = 1; i < candidate_tokens.size(); ++i) {
            if (candidate_tokens[i].loss_prob < best.loss_prob) {
                best = candidate_tokens[i];
            } else if (std::abs(candidate_tokens[i].loss_prob - best.loss_prob) < 0.05) {
                if (candidate_tokens[i].adx > best.adx) {
                    best = candidate_tokens[i];
                }
            }
        }
        return best;
    }

    bool is_usd_symbol(const std::string& symbol) const {
        return symbol.find("USD") != std::string::npos || symbol.find("US") != std::string::npos;
    }
};

} // namespace v9
