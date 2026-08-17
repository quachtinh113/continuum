#pragma once

#include "v9/core/types.hpp"
#include <vector>
#include <cmath>
#include <algorithm>

namespace v9 {

struct OrderBlock {
    double top{0.0};
    double bottom{0.0};
    Signal direction{Signal::HOLD};
    uint64_t timestamp{0};
    bool is_mitigated{false};
};

struct FairValueGap {
    double top{0.0};
    double bottom{0.0};
    Signal direction{Signal::HOLD};
    uint64_t timestamp{0};
    bool is_filled{false};
};

class SMCEngine {
public:
    SMCEngine() = default;

    /**
     * @brief Phát hiện vùng Order Block (Khối lệnh tổ chức) trên chuỗi nến.
     */
    std::vector<OrderBlock> detect_order_blocks(const std::vector<Candle>& candles, int lookback = 20) const {
        std::vector<OrderBlock> blocks;
        if (candles.size() < 4) return blocks;

        size_t start_idx = candles.size() > static_cast<size_t>(lookback) ? candles.size() - lookback : 0;

        for (size_t i = start_idx; i + 2 < candles.size(); ++i) {
            const auto& c1 = candles[i];
            const auto& c2 = candles[i + 1];
            const auto& c3 = candles[i + 2];

            // Bullish Order Block: Nến giảm trước một cụm tăng mạnh phá đỉnh
            if (c1.close < c1.open && c2.close > c2.open && c3.close > c1.high) {
                OrderBlock ob;
                ob.top = c1.high;
                ob.bottom = c1.low;
                ob.direction = Signal::BUY;
                ob.timestamp = c1.timestamp;
                blocks.push_back(ob);
            }
            // Bearish Order Block: Nến tăng trước một cụm giảm mạnh phá đáy
            else if (c1.close > c1.open && c2.close < c2.open && c3.close < c1.low) {
                OrderBlock ob;
                ob.top = c1.high;
                ob.bottom = c1.low;
                ob.direction = Signal::SELL;
                ob.timestamp = c1.timestamp;
                blocks.push_back(ob);
            }
        }
        return blocks;
    }

    /**
     * @brief Phát hiện khoảng trống giá trị hợp lý (Fair Value Gap - FVG 3 nến).
     */
    std::vector<FairValueGap> detect_fvg(const std::vector<Candle>& candles, int lookback = 20) const {
        std::vector<FairValueGap> fvgs;
        if (candles.size() < 3) return fvgs;

        size_t start_idx = candles.size() > static_cast<size_t>(lookback) ? candles.size() - lookback : 0;

        for (size_t i = start_idx; i + 2 < candles.size(); ++i) {
            const auto& c1 = candles[i];
            const auto& c3 = candles[i + 2];

            // Bullish FVG: Đáy nến 3 cao hơn Đỉnh nến 1
            if (c3.low > c1.high) {
                FairValueGap fvg;
                fvg.bottom = c1.high;
                fvg.top = c3.low;
                fvg.direction = Signal::BUY;
                fvg.timestamp = candles[i + 1].timestamp;
                fvgs.push_back(fvg);
            }
            // Bearish FVG: Đỉnh nến 3 thấp hơn Đáy nến 1
            else if (c3.high < c1.low) {
                FairValueGap fvg;
                fvg.top = c1.low;
                fvg.bottom = c3.high;
                fvg.direction = Signal::SELL;
                fvg.timestamp = candles[i + 1].timestamp;
                fvgs.push_back(fvg);
            }
        }
        return fvgs;
    }
};

} // namespace v9
