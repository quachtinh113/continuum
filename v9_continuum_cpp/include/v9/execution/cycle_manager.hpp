#pragma once

#include "v9/core/types.hpp"
#include "v9/layers/position_sizer.hpp"
#include "v9/ml/ml_gatekeeper.hpp"
#include <vector>
#include <map>
#include <iostream>
#include <cmath>

namespace v9 {

enum class CycleActionType {
    NONE,
    CLOSE_PROFIT_TARGET,
    CLOSE_TRAILING_BE,
    CLOSE_12H_CUTOFF,
    ADD_DCA_LAYER,
    CLOSE_DCA_LAYER
};

struct CycleAction {
    CycleActionType type{CycleActionType::NONE};
    std::string symbol{""};
    uint64_t ticket{0};
    double price{0.0};
    double lot{0.0};
    std::string reason{""};
};

class CycleManager {
public:
    PositionSizer position_sizer{};
    MLSignalEngine ml_engine{};

    CycleManager() = default;

    /**
     * @brief Giám sát và đánh giá chu kỳ lệnh active theo từng tick giá.
     */
    std::vector<CycleAction> evaluate_cycle(
        ActiveCycle& cycle,
        double current_price,
        double current_spread_pips,
        uint64_t current_time,
        double base_target_usd = 180.0
    ) {
        std::vector<CycleAction> actions;

        // Cập nhật thời gian nắm giữ (holding hours)
        if (current_time > cycle.entry_time) {
            cycle.holding_hours = (current_time - cycle.entry_time) / 3600.0;
        }

        // Cập nhật mức giá cực trị để theo dõi Trailing Breakeven
        if (cycle.direction == Signal::BUY) {
            cycle.extreme_price = std::max(cycle.extreme_price, current_price);
        } else {
            cycle.extreme_price = (cycle.extreme_price == 0.0) ? current_price : std::min(cycle.extreme_price, current_price);
        }

        // 1. Tính toán trung bình giá và tổng lot có Zero-Division Safeguard
        double base_lot = std::max(cycle.base_lot > 0.0 ? cycle.base_lot : 0.01, 0.01);
        cycle.base_lot = base_lot;
        double total_lots = cycle.get_total_lots();
        double avg_entry_price = cycle.get_avg_entry_price();

        // 2. Tính toán mục tiêu chốt lời ròng (Net Profit Target)
        SymbolSpec spec = SymbolRegistry::get_spec(cycle.symbol);
        double target_scale = spec.category == "INDEX" ? 15.0 : base_target_usd;
        double target_gross_usd = target_scale * (total_lots / base_lot);

        double spread_cost = current_spread_pips * spec.pip_size * total_lots * spec.contract_size;
        double commission = 7.0 * total_lots; // $7/lot ECN round-trip

        double net_profit_target = position_sizer.calculate_target_exit_price(
            cycle.direction,
            avg_entry_price,
            total_lots,
            cycle.symbol,
            target_gross_usd,
            spread_cost,
            commission
        );

        // 3. Kiểm tra chạm mục tiêu chốt lời (Target Profit Check)
        bool is_profit_hit = (cycle.direction == Signal::BUY && current_price >= net_profit_target) ||
                             (cycle.direction == Signal::SELL && current_price <= net_profit_target);

        if (is_profit_hit && cycle.holding_hours > 0.1) {
            CycleAction act;
            act.type = CycleActionType::CLOSE_PROFIT_TARGET;
            act.symbol = cycle.symbol;
            act.ticket = cycle.ticket;
            act.price = current_price;
            act.lot = total_lots;
            act.reason = "TARGET_PROFIT_MET";
            actions.push_back(act);
            return actions;
        }

        // 4. Kiểm tra Trailing Breakeven (Kích hoạt khi lãi > 1.5 ATR)
        double be_activation_distance = 1.5 * cycle.atr;
        if (!cycle.trailing_active) {
            if (cycle.direction == Signal::BUY && (current_price - cycle.entry_price) >= be_activation_distance) {
                cycle.trailing_active = true;
            } else if (cycle.direction == Signal::SELL && (cycle.entry_price - current_price) >= be_activation_distance) {
                cycle.trailing_active = true;
            }
        } else {
            // Khi trailing đang bật: Nếu giá quay lại chạm điểm hòa vốn (entry_price + buffer) -> Đóng lệnh bảo toàn vốn
            double be_price = cycle.entry_price;
            if ((cycle.direction == Signal::BUY && current_price <= be_price) ||
                (cycle.direction == Signal::SELL && current_price >= be_price)) {
                CycleAction act;
                act.type = CycleActionType::CLOSE_TRAILING_BE;
                act.symbol = cycle.symbol;
                act.ticket = cycle.ticket;
                act.price = current_price;
                act.lot = total_lots;
                act.reason = "TRAILING_BREAKEVEN_HIT";
                actions.push_back(act);
                return actions;
            }
        }

        // 5. Kiểm tra giới hạn thời gian nắm giữ 12H ML Cutoff
        if (cycle.holding_hours >= 12.0) {
            double risk_score = ml_engine.predict_loss_probability(cycle.features);
            if (risk_score >= 0.65) {
                // Rủi ro cao sau 12H -> Cắt vị thế chủ động để giải phóng vốn
                CycleAction act;
                act.type = CycleActionType::CLOSE_12H_CUTOFF;
                act.symbol = cycle.symbol;
                act.ticket = cycle.ticket;
                act.price = current_price;
                act.lot = total_lots;
                act.reason = "12H_HIGH_RISK_CUTOFF";
                actions.push_back(act);
                return actions;
            }
        }

        return actions;
    }
};

} // namespace v9
