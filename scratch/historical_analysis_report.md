# 🔬 Báo Cáo Phân Tích Lịch Sử & Kiểm Tra Rủi Ro V9

**Thời gian thực hiện:** 2026-07-18 20:52:45 Local

## 1. 📊 Task A: Stress-Test Riêng Cho Cặp XAUUSDm (Vàng)
Kiểm tra xem hiệu suất vượt trội của XAUUSDm trong tuần vừa rồi (+$136.45) có phải là xu hướng bền vững dựa trên dữ liệu lịch sử 5.5 tháng qua hay không.

### Chỉ số Hiệu suất XAUUSDm (Jan 1, 2026 - Jun 15, 2026)
- **Khởi điểm:** $1000.00
- **Lợi nhuận ròng:** $-2574.57 (-257.46%)
- **Số lượng chu kỳ (Cycles):** 413
- **Tỷ lệ thắng (Win Rate):** 22.52%
- **Hệ số lợi nhuận (Profit Factor):** 0.46
- **Sụt giảm vốn tối đa (Max Drawdown):** $2675.29 (265.02%)
- **Hệ số hồi phục (Recovery Factor):** -0.96
- **Thời gian giữ lệnh trung bình:** 1.9h
- **Số lớp DCA tối đa đạt tới:** 2

### Lý do đóng chu kỳ (Exit Reasons Breakdown)
- **BREAK_EVEN:** 281
- **TAKE_PROFIT:** 93
- **HARD_STOP_LOSS:** 39

## 2. 💱 Task C: Đánh Giá Phân Bổ Vốn (Portfolio Asset Allocation)
So sánh hiệu suất độc lập của 12 cặp tài sản dưới cùng một cấu hình `.env` để xác định những cặp yếu kém có thể loại bỏ nhằm tối ưu hóa dòng vốn.

### Bảng Xếp Hạng Hiệu Suất Độc Lập Các Cặp Tài Sản (Bắt đầu với $1000)

| Xếp Hạng | Cặp (Symbol) | Lợi Nhuận ($) | Win Rate (%) | Profit Factor | Max Drawdown ($) | Max DD (%) | Recovery Factor | Số Lệnh (Cycles) | Lớp DCA Max |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | **AUDUSD** | -126.35 | 0.00% | 0.00 | 207.84 | 18.89% | -0.61 | 53 | 0 |
| 2 | **US500** | -246.88 | 6.87% | 0.14 | 247.18 | 24.72% | -1.00 | 422 | 2 |
| 3 | **USDCAD** | -379.19 | 0.00% | 0.00 | 470.97 | 43.16% | -0.81 | 216 | 0 |
| 4 | **USDCHF** | -574.23 | 0.00% | 0.00 | 788.73 | 64.95% | -0.73 | 220 | 0 |
| 5 | **GBPUSD** | -580.68 | 0.00% | 0.00 | 647.37 | 60.93% | -0.90 | 168 | 0 |
| 6 | **US100** | -649.75 | 18.90% | 0.40 | 679.01 | 67.86% | -0.96 | 471 | 2 |
| 7 | **US30** | -658.67 | 17.56% | 0.28 | 658.67 | 65.87% | -1.00 | 262 | 2 |
| 8 | **EURUSD** | -696.41 | 0.00% | 0.00 | 700.82 | 70.08% | -0.99 | 270 | 0 |
| 9 | **NZDUSD** | -724.07 | 0.00% | 0.00 | 808.20 | 74.83% | -0.90 | 246 | 0 |
| 10 | **USDJPY** | -868.95 | 0.00% | 0.00 | 871.87 | 86.93% | -1.00 | 368 | 0 |
| 11 | **BTCUSD** | -931.22 | 10.49% | 0.43 | 954.18 | 95.42% | -0.98 | 448 | 2 |
| 12 | **XAUUSD** | -2574.57 | 22.52% | 0.46 | 2675.29 | 265.02% | -0.96 | 413 | 2 |

> [!TIP]
> **Khuyến nghị phân bổ vốn:** Dựa trên kết quả backtest, rổ tài sản của bạn có **0** cặp tạo lợi nhuận dương và **12** cặp tạo lợi nhuận âm trong 5.5 tháng qua. Bạn nên cân nhắc tắt bớt các cặp yếu như: **AUDUSD, US500, USDCAD, USDCHF, GBPUSD, US100, US30, EURUSD, NZDUSD, USDJPY, BTCUSD, XAUUSD** để tập trung ký quỹ cho các cặp mạnh như ****.

## 3. 🚨 Task B: Kiểm Tra Cơ Chế Cắt Lỗ (Risk Layer) & Lỗi Kết Nối IPC (July 16-17)
Phân tích xem các sự cố mất kết nối MT5 (IPC timeout) vào ngày 16 và 17/07 có gây ảnh hưởng hay làm trễ tiến trình đóng lệnh (SL/TP) của bot hay không.

### Chi tiết các đợt đóng chu kỳ giao dịch gần cảnh báo lỗi kết nối (Window 10 phút)

| Thời Gian (UTC) | Cặp | Chiều | Lý Do Đóng | Giá Đóng | Số Lỗi Kết Nối Gần Đó | Chi Tiết Lỗi Gần Nhất |
| :--- | :--- | :--- | :--- | :---: | :---: | :--- |
| 00:00:03 | XAUUSD | SELL | TRAILING_BE_EXIT | 3985.471 | 4 | `[00:03:47] MT5 initialize failed: (-10005, 'IPC timeout')` |

### Nhận định về rủi ro cắt lỗ trễ:
- **Tổng số lỗi kết nối MT5 / IPC ghi nhận trong 2 ngày:** 69 lần.
- **Số lần mất kết nối hoàn toàn (phải thử lại 3 lần thất bại):** 17 lần.
- ⚠️ **Cảnh báo:** Có **1** sự kiện đóng lệnh xảy ra rất sát thời điểm hệ thống ghi nhận lỗi kết nối MT5/IPC. Điều này xác thực giả thuyết rằng các lỗi IPC timeout có thể gây ra hiện tượng trượt giá (slippage) hoặc làm chậm trễ lệnh đóng của bot thực tế trên MT5 so với thời điểm kích hoạt trong code.
