#include "v9/core/types.hpp"
#include "v9/config/symbols.hpp"
#include "v9/config/settings.hpp"
#include "v9/layers/indicators.hpp"
#include "v9/layers/position_sizer.hpp"
#include "v9/layers/kalman.hpp"
#include "v9/layers/smc.hpp"
#include "v9/core/governor.hpp"
#include "v9/ml/ml_gatekeeper.hpp"
#include "v9/execution/cycle_manager.hpp"

#include <iostream>
#include <iomanip>
#include <chrono>
#include <csignal>
#include <atomic>

#ifdef _WIN32
#include <windows.h>
#define SLEEP_MS(ms) Sleep(ms)
#else
#include <unistd.h>
#define SLEEP_MS(ms) usleep((ms) * 1000)
#endif

using namespace v9;

std::atomic<bool> g_running{true};

void signal_handler(int signum) {
    std::cout << "\n[INFO] Received shutdown signal (" << signum << "). Gracefully stopping bot..." << std::endl;
    g_running = false;
}

#ifdef _WIN32
HANDLE g_mutex = NULL;

bool acquire_single_instance_mutex() {
    const char* mutex_name = "Global\\V9_CONTINUUM_CPP_SINGLE_INSTANCE_MUTEX";
    g_mutex = CreateMutexA(NULL, TRUE, mutex_name);
    if (g_mutex == NULL || GetLastError() == ERROR_ALREADY_EXISTS) {
        std::cerr << "[ERROR] Another V9 Continuum C++ instance is already running! (Mutex: " << mutex_name << ")" << std::endl;
        return false;
    }
    std::cout << "[INFO] Acquired Single-Instance Mutex Lock (" << mutex_name << ")" << std::endl;
    return true;
}

void release_single_instance_mutex() {
    if (g_mutex != NULL) {
        ReleaseMutex(g_mutex);
        CloseHandle(g_mutex);
        g_mutex = NULL;
    }
}
#endif

int main(int argc, char* argv[]) {
    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);

#ifdef _WIN32
    if (!acquire_single_instance_mutex()) {
        return 1;
    }
#endif

    std::cout << "=================================================================" << std::endl;
    std::cout << "        CONTINUUM V9: INSTITUTIONAL MODERN C++ BOT ENGINE        " << std::endl;
    std::cout << "=================================================================" << std::endl;
    std::cout << " Engine Version     : v9.2 C++20 Core" << std::endl;
    std::cout << " Sizing Model       : Fixed Fractional Risk 0.5% + Micro-Guard" << std::endl;
    std::cout << " Portfolio Watchlist: XAUUSD, USDJPY, AUDUSD, USDCAD" << std::endl;
    std::cout << " ML Filter Gate     : Meta-Labeling Decision Ensemble (Veto >= 0.80)" << std::endl;
    std::cout << " Governor Matrix    : USD Exposure <= 2 | Daily Drawdown Stop: 5%" << std::endl;
    std::cout << " Status             : RUNNING (Press Ctrl+C to Stop)" << std::endl;
    std::cout << "=================================================================\n" << std::endl;

    Settings settings;
    PositionSizer sizer;
    PortfolioGovernor governor;
    MLSignalEngine ml_engine(settings.ml_veto_threshold);
    CycleManager cycle_manager;

    double simulated_equity = 883.44; // Sync with MT5 Trial account balance
    double start_of_day_balance = 883.44;
    std::map<std::string, ActiveCycle> active_cycles;

    uint64_t loop_count = 0;

    while (g_running) {
        loop_count++;
        auto now = std::chrono::system_clock::now();
        auto now_c = std::chrono::system_clock::to_time_t(now);

        // Hiển thị nhịp đập Heartbeat định kỳ
        if (loop_count % 6 == 1) {
            std::cout << "[" << std::put_time(std::localtime(&now_c), "%H:%M:%S") 
                      << "] [HEARTBEAT] Loop #" << loop_count 
                      << " | Equity: $" << std::fixed << std::setprecision(2) << simulated_equity
                      << " | Active Cycles: " << active_cycles.size()
                      << " | Status: " << governor.system_status << std::endl;
        }

        // Vòng lặp nghỉ 10 giây
        SLEEP_MS(10000);
    }

#ifdef _WIN32
    release_single_instance_mutex();
#endif

    std::cout << "[INFO] V9 Continuum C++ Bot stopped cleanly. Goodbye!" << std::endl;
    return 0;
}
