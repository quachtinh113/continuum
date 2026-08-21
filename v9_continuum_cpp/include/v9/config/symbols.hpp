#pragma once

#include <string>
#include <map>
#include <stdexcept>

namespace v9 {

struct SymbolSpec {
    std::string name;          // Broker symbol name (e.g., EURUSDm, XAUUSDm, USTECm)
    std::string category;      // "FX", "GOLD", "INDEX", "CRYPTO"
    double pip_size;           // 0.0001 for FX, 0.01 for JPY/Gold/Indices
    double default_lot;        // 0.01
    double spread_limit;       // Pips limit
    double contract_size;      // 100,000 for FX, 100 for Gold, 1 for Indices
    std::string description;   // Mô tả tài sản
};

class SymbolRegistry {
public:
    static const std::map<std::string, SymbolSpec>& get_all_symbols() {
        static const std::map<std::string, SymbolSpec> registry = {
            // ── FX Majors ──
            {"EURUSD", {"EURUSDm", "FX", 0.0001, 0.01, 5.0, 100000.0, "Euro / US Dollar"}},
            {"GBPUSD", {"GBPUSDm", "FX", 0.0001, 0.01, 5.0, 100000.0, "British Pound / US Dollar"}},
            {"USDJPY", {"USDJPYm", "FX", 0.01,   0.01, 5.0, 100000.0, "US Dollar / Japanese Yen"}},
            {"AUDUSD", {"AUDUSDm", "FX", 0.0001, 0.01, 5.0, 100000.0, "Australian Dollar / US Dollar"}},
            {"USDCHF", {"USDCHFm", "FX", 0.0001, 0.01, 5.0, 100000.0, "US Dollar / Swiss Franc"}},
            {"USDCAD", {"USDCADm", "FX", 0.0001, 0.01, 5.0, 100000.0, "US Dollar / Canadian Dollar"}},
            {"NZDUSD", {"NZDUSDm", "FX", 0.0001, 0.01, 5.0, 100000.0, "New Zealand Dollar / US Dollar"}},

            // ── Gold ──
            {"XAUUSD", {"XAUUSDm", "GOLD", 0.01, 0.01, 50.0, 100.0, "Gold / US Dollar"}},

            // ── US Indices ──
            {"US30",  {"US30m",  "INDEX", 0.01, 0.01, 50.0, 1.0, "Dow Jones 30"}},
            {"US100", {"USTECm", "INDEX", 0.01, 0.01, 50.0, 1.0, "NASDAQ 100"}},
            {"US500", {"US500m", "INDEX", 0.01, 0.01, 50.0, 1.0, "S&P 500"}},

            // ── Crypto ──
            {"BTCUSD", {"BTCUSDm", "CRYPTO", 0.01, 0.01, 100.0, 1.0, "Bitcoin / US Dollar"}}
        };
        return registry;
    }

    static SymbolSpec get_spec(const std::string& symbol) {
        const auto& all = get_all_symbols();
        auto it = all.find(symbol);
        if (it != all.end()) {
            return it->second;
        }
        // Fallback default
        return {"" + symbol + "m", "FX", 0.0001, 0.01, 10.0, 100000.0, "Unknown Symbol"};
    }

    static std::vector<std::string> get_active_super_elite_universe() {
        return {"AUDUSD", "NZDUSD", "USDJPY", "XAUUSD", "US30", "BTCUSD"};
    }
};

} // namespace v9
