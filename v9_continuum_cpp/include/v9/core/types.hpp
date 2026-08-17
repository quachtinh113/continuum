#pragma once

#include <string>
#include <vector>
#include <map>
#include <cstdint>
#include <chrono>
#include <iomanip>
#include <sstream>

namespace v9 {

// ── 1. Kiểu dữ liệu Nến (Candlestick Bar) ─────────────────────
struct Candle {
    uint64_t timestamp{0}; // Unix epoch (seconds)
    double open{0.0};
    double high{0.0};
    double low{0.0};
    double close{0.0};
    double volume{0.0};

    Candle() = default;
    Candle(uint64_t ts, double o, double h, double l, double c, double v = 0.0)
        : timestamp(ts), open(o), high(h), low(l), close(c), volume(v) {}
};

// ── 2. Tín hiệu và Phiên giao dịch (Signal & Session Enums) ────
enum class Signal {
    HOLD = 0,
    BUY = 1,
    SELL = -1
};

inline std::string signal_to_string(Signal sig) {
    switch (sig) {
        case Signal::BUY: return "BUY";
        case Signal::SELL: return "SELL";
        default: return "HOLD";
    }
}

enum class Session {
    OFF = -1,
    ASIA = 0,
    EUROPE = 1,
    US = 2,
    OVERLAP_ASIA_EU = 3,
    OVERLAP_EU_US = 4
};

inline std::string session_to_string(Session sess) {
    switch (sess) {
        case Session::ASIA: return "ASIA";
        case Session::EUROPE: return "EUROPE";
        case Session::US: return "US";
        case Session::OVERLAP_ASIA_EU: return "OVERLAP_ASIA_EU";
        case Session::OVERLAP_EU_US: return "OVERLAP_EU_US";
        default: return "OFF";
    }
}

// ── 3. Quyết định Quản trị rủi ro (Risk Decision) ─────────────
struct RiskDecision {
    bool approved{false};
    std::string reason{""};
    std::string status_code{"BLOCKED"};

    RiskDecision() = default;
    RiskDecision(bool app, const std::string& r, const std::string& code = "")
        : approved(app), reason(r), status_code(code.empty() ? (app ? "APPROVED" : "BLOCKED") : code) {}
};

// ── 4. Token Tín hiệu cạnh tranh (Signal Candidate Token) ───────
struct OrderToken {
    std::string symbol{""};
    Signal direction{Signal::HOLD};
    double price{0.0};
    double atr{0.0};
    double spread{0.0};
    double adx{0.0};
    double loss_prob{0.0};
    std::string reason{""};
    std::map<std::string, double> features{};
};

// ── 5. Cấu trúc DCA Tầng (DCA Layer) ───────────────────────────
struct DcaLayer {
    uint64_t ticket{0};
    double entry_price{0.0};
    double lot{0.0};
    double pips_distance{0.0};
    uint64_t entry_time{0};
};

// ── 6. Chu kỳ lệnh đang hoạt động (Active Lifecycle Cycle) ─────
struct ActiveCycle {
    std::string symbol{""};
    Signal direction{Signal::HOLD};
    double entry_price{0.0};
    double base_lot{0.01};
    uint64_t ticket{0};
    uint64_t entry_time{0}; // Unix timestamp
    std::vector<DcaLayer> dca_layers{};
    double holding_hours{0.0};
    double atr{0.0};
    bool is_extended{false};
    bool trailing_active{false};
    double extreme_price{0.0};
    std::map<std::string, double> features{};

    double get_total_lots() const {
        double total = base_lot > 0.0 ? base_lot : 0.01;
        for (const auto& layer : dca_layers) {
            total += layer.lot > 0.0 ? layer.lot : base_lot;
        }
        return total;
    }

    double get_avg_entry_price() const {
        double total_lot = get_total_lots();
        if (total_lot <= 0.0) return entry_price;

        double total_cost = entry_price * (base_lot > 0.0 ? base_lot : 0.01);
        for (const auto& layer : dca_layers) {
            total_cost += layer.entry_price * (layer.lot > 0.0 ? layer.lot : base_lot);
        }
        return total_cost / total_lot;
    }
};

// ── 7. Bản ghi Lệnh đã đóng (Closed Trade Record) ──────────────
struct TradeRecord {
    uint64_t ticket{0};
    std::string symbol{""};
    Signal direction{Signal::HOLD};
    double entry_price{0.0};
    double exit_price{0.0};
    double lot{0.0};
    double final_pnl{0.0};
    uint64_t entry_time{0};
    uint64_t exit_time{0};
    std::string exit_reason{""};
    double holding_hours{0.0};
};

} // namespace v9
