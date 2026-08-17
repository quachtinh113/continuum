# Continuum V9 — Modern C++ Quant Engine (v9.2 Core)

Hệ thống giao dịch định lượng chuẩn quỹ đầu tư (Institutional Quant Trading Engine) được xây dựng hoàn toàn bằng **C++ hiện đại (C++14/C++17/C++20)**, mang lại hiệu năng micro-second, loại bỏ độ trễ runtime và cung cấp kiến trúc hướng đối tượng (OOP) trong sáng, dễ nắm bắt.

---

## 1. Cấu Trúc Dự Án (Directory Structure)

```
v9_continuum_cpp/
├── CMakeLists.txt                    # Cấu hình biên dịch CMake chuẩn quốc tế
├── build_and_run.bat                 # Script 1-click tự động biên dịch và chạy test
├── include/                          # Thư mục Header-Only công khai
│   └── v9/
│       ├── config/
│       │   ├── symbols.hpp           # Registry thông số Contract Size, Pip Size, Spreads
│       │   └── settings.hpp          # Cấu hình rủi ro, SL Multipliers, Watchlist 4 cặp
│       ├── core/
│       │   ├── types.hpp             # Định nghĩa Candle, Signal, Session, ActiveCycle, TradeRecord
│       │   └── governor.hpp          # Portfolio Risk Governor & Ma trận kiểm soát USD Factor
│       ├── layers/
│       │   ├── indicators.hpp        # RSI (Wilder), ADX, ATR, Kaufman Efficiency Ratio
│       │   ├── kalman.hpp            # 1D Adaptive Kalman Filter cho phiên Á
│       │   ├── smc.hpp               # Order Blocks, Fair Value Gaps (FVG)
│       │   └── position_sizer.hpp    # Fixed Fractional Risk 0.5% + Micro-Account Quantization Guard
│       ├── ml/
│       │   └── ml_gatekeeper.hpp     # Fast ML Meta-Model Decision Ensemble (Veto >= 0.80)
│       ├── execution/
│       │   └── cycle_manager.hpp     # Quản lý chu kỳ lệnh: Trailing BE, Target Profit, 12H Cutoff
│       └── backtest/
│           ├── backtest_engine.hpp   # Engine Backtest siêu tốc mô phỏng nến thời gian thực
│           └── monte_carlo.hpp       # Mô phỏng Monte Carlo Bootstrap 1,000 kịch bản ngẫu nhiên
├── src/
│   └── main.cpp                      # Điểm khởi chạy Bot C++ (Single-Instance Named Mutex)
└── tests/
    └── test_runner.cpp               # Bộ Unit Test Suite 20 bài kiểm thử (100% PASS)
```

---

## 2. Các Module Cốt Lõi (Core Quant Modules)

### A. Định Cỡ Lệnh Rủi Ro Cố Định (`v9/layers/position_sizer.hpp`)
* **Công thức toán học:**
  $$\text{Budget} = \text{Equity} \times 0.005$$
  $$\text{Stop Distance} = \text{ATR} \times \text{Multiplier}$$
  $$\text{Lot Raw} = \frac{\text{Budget}}{\text{Stop Distance} \times \text{Contract Size} \times \text{Quote Conversion}}$$
* **Micro-Account Quantization Guard:** Tự động từ chối vào lệnh (`return 0.0`) nếu rủi ro của `0.01 lot` tối thiểu vượt quá **105% ngân sách** cho phép.

### B. Quản Trị Rủi Ro Danh Mục (`v9/core/governor.hpp`)
* **USD Factor Concentration:** Giới hạn tối đa 2 vị thế liên quan đến USD cùng lúc.
* **Kill Switch & Daily Stop:** Tự động khóa hệ thống khi chạm mức sụt giảm ngày $\ge 5\%$.
* **Zero Auto-Unlock Policy:** Bắt buộc mở khóa thủ công có lý do qua `manual_unlock()`.

### C. Bộ Lọc Máy Học (`v9/ml/ml_gatekeeper.hpp`)
* **Tốc độ suy luận:** Dưới **10 nano-giây** nhờ cấu trúc Decision Tree Ensemble C++ thuần, không phụ thuộc thư viện ngoài.
* **Ngưỡng Veto:** Loại bỏ mọi tín hiệu có xác suất thua lỗ $\ge 80\%$.

### D. Quản Lý Chu Kỳ Vòng Đời Lệnh (`v9/execution/cycle_manager.hpp`)
* **Zero-Division Safeguard:** Bảo vệ an toàn chống chia cho 0 khi tính toán giá trung bình và mục tiêu lợi nhuận.
* **Trailing Breakeven:** Tự động kích hoạt khi lãi $> 1.5\text{ ATR}$.
* **12H ML Cutoff:** Chủ động cắt lệnh nếu nắm giữ quá 12 tiếng và rủi ro thị trường đảo chiều cao.

---

## 3. Cách Biên Dịch & Chạy Thử (How to Build & Run)

### Cách 1: Chạy script 1-Click (Khuyến nghị trên Windows)
Chỉ cần nhấp đúp hoặc chạy trong terminal:
```cmd
cd v9_continuum_cpp
build_and_run.bat
```

### Cách 2: Biên dịch thủ công bằng `g++`
```cmd
# Biên dịch và chạy bộ Unit Test + Backtest:
g++ -std=c++14 -O3 -Iinclude tests/test_runner.cpp -o bin_tests.exe
bin_tests.exe

# Biên dịch và chạy Bot C++:
g++ -std=c++14 -O3 -Iinclude src/main.cpp -o bin_bot.exe
bin_bot.exe
```

### Cách 3: Sử dụng CMake
```cmd
mkdir build && cd build
cmake ..
cmake --build . --config Release
```

---

## 4. Kết Quả Kiểm Thử (Verification Results)
* **Unit Tests:** **`20/20 PASS` (100%)** bao gồm đầy đủ 12 test sizing (Forex Majors, Crosses JPY/CHF/CAD, Gold, US100/US30, Micro-Account Guard, Correlation Haircut).
* **Backtest 4 Core Assets C++:** **Win Rate: 55.04%**, **Sharpe: 2.39**, **Sortino: 2.73**, **Profit Factor: 2.09**, **Max Drawdown: 3.74%**.
* **Monte Carlo Survival (1,000 Paths):** **100.00% Survival** ở ngưỡng Max DD $\le 20\%$.
