#pragma once

#include "v9/core/types.hpp"
#include "v9/config/symbols.hpp"
#include <string>
#include <vector>
#include <cmath>
#include <algorithm>

namespace v9 {

class PositionSizer {
public:
    PositionSizer() = default;

    /**
     * @brief Tính toán khối lượng vào lệnh chuẩn Fixed Fractional Risk (0.5% Vốn).
     * @param equity Số dư tài sản hiện tại ($).
     * @param atr Giá trị ATR(14) trên khung nến H1.
     * @param symbol Mã cặp tiền/tài sản giao dịch.
     * @param risk_percent Tỷ lệ rủi ro trên mỗi lệnh (mặc định 0.5%).
     * @param ml_score Điểm dự báo rủi ro từ mô hình ML (0.0 -> 1.0).
     * @param current_price Giá thị trường hiện tại của tài sản.
     * @param open_symbols Danh sách các mã tài sản đang có vị thế mở.
     * @param atr_multiplier Hệ số nhân khoảng cách Stop Loss (mặc định 1.5).
     * @return Khối lượng Lot chuẩn xác (làm tròn 2 chữ số thập phân). Trả về 0.0 nếu vượt ngân sách rủi ro.
     */
    double calculate_lot_size(
        double equity,
        double atr,
        const std::string& symbol,
        double risk_percent = 0.5,
        double ml_score = 0.5,
        double current_price = 0.0,
        const std::vector<std::string>& open_symbols = {},
        double atr_multiplier = 1.5
    ) const {
        if (equity <= 0.0 || atr <= 0.0) {
            return 0.0;
        }

        // 1. Lấy thông số kỹ thuật của tài sản
        SymbolSpec spec = SymbolRegistry::get_spec(symbol);
        double contract_size = spec.contract_size;
        double stop_distance = atr * atr_multiplier;

        // 2. Tính toán tỷ lệ quy đổi tiền tệ định giá (Quote Currency Conversion to USD)
        double quote_conv = 1.0;
        if (spec.category == "FX") {
            if (symbol.find("JPY") != std::string::npos || symbol.find("CHF") != std::string::npos || symbol.find("CAD") != std::string::npos) {
                if (current_price > 0.0) {
                    quote_conv = 1.0 / current_price;
                }
            }
        }

        // 3. Ngân sách rủi ro tối đa cho lệnh (0.5% Equity)
        double risk_budget = equity * (risk_percent / 100.0);

        // 4. Haircut giảm 30% khối lượng nếu danh mục đang mở vị thế tương quan cùng nhóm
        double correlation_multiplier = 1.0;
        for (const auto& open_sym : open_symbols) {
            if (open_sym == symbol) continue;
            SymbolSpec open_spec = SymbolRegistry::get_spec(open_sym);
            if (open_spec.category == spec.category) {
                correlation_multiplier = 0.70;
                break;
            }
        }
        risk_budget *= correlation_multiplier;

        // 5. Tính rủi ro cho mỗi 1.0 Lot tiêu chuẩn
        double risk_per_full_lot = stop_distance * contract_size * quote_conv;
        if (risk_per_full_lot <= 0.0) {
            return 0.0;
        }

        // 6. Tính toán khối lượng Raw Lot
        double raw_lot = risk_budget / risk_per_full_lot;

        // 7. MICRO-ACCOUNT QUANTIZATION GUARD:
        // Nếu khối lượng tối thiểu 0.01 lot gây rủi ro vượt quá 105% ngân sách -> Từ chối vào lệnh (return 0.0)
        double min_lot = 0.01;
        double risk_at_min_lot = min_lot * risk_per_full_lot;
        if (raw_lot < min_lot) {
            if (risk_at_min_lot > risk_budget * 1.05) {
                return 0.0; // Từ chối vào lệnh để bảo vệ tài khoản nhỏ
            }
            return min_lot;
        }

        // Làm tròn 2 chữ số thập phân
        double lot = std::floor(raw_lot * 100.0) / 100.0;
        return std::max(min_lot, lot);
    }

    /**
     * @brief Tính giá mục tiêu chốt lời tối ưu sau khi trừ chi phí Spread & Commission.
     */
    double calculate_target_exit_price(
        Signal direction,
        double avg_entry_price,
        double total_lots,
        const std::string& symbol,
        double target_gross_usd,
        double spread_cost = 0.0,
        double commission = 0.0
    ) const {
        if (total_lots <= 0.0) return avg_entry_price;

        SymbolSpec spec = SymbolRegistry::get_spec(symbol);
        double net_needed_usd = target_gross_usd + spread_cost + commission;
        double price_delta = net_needed_usd / (total_lots * spec.contract_size);

        if (direction == Signal::BUY) {
            return avg_entry_price + price_delta;
        } else {
            return avg_entry_price - price_delta;
        }
    }
};

} // namespace v9
