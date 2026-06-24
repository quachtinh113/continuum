# 🧠 KHO BÁU TRI THỨC VẬN HÀNH & KINH NGHIỆM HỆ THỐNG (V9 CONTINUUM)

Tài liệu này tổng hợp các bài học kinh nghiệm vận hành hệ thống, lỗi thiết kế, và các điểm yếu phát sinh trong thực tế giao dịch hàng ngày của bot V9 Continuum.

---

## 📅 2026-06-22 (Phiên vận hành và khôi phục hệ thống)

### 🧠 I. BÀI HỌC KINH NGHIỆM ĐẮT GIÁ TRONG NGÀY

* **Đường dẫn khởi động Script (Working Directory & Path Fallbacks):**
  * *Vấn đề:* Việc copy file `.bat` chạy trực tiếp ngoài Desktop làm thay đổi thư mục làm việc của Python sang Desktop, dẫn tới lỗi `ModuleNotFoundError: No module named 'v9_continuum'` và dừng bot đột ngột.
  * *Bài học:* Không giả định script luôn được chạy đúng vị trí. Luôn thiết kế cơ chế tự động kiểm tra thư mục (`Fallback Directory Check`) để tự động `cd` về thư mục dự án gốc, hoặc khuyên người dùng chỉ sử dụng **Shortcut** thay vì copy file.

* **Giám sát hoạt động thực tế của Bot (Process Monitoring):**
  * *Vấn đề:* Cửa sổ CMD mở không có nghĩa là bot đang chạy. Tiến trình Python có thể đã crash từ trước và bị kẹt ở lệnh `pause` do chạm giới hạn `MAX_RESTARTS=50` của file `.bat`.
  * *Bài học:* Cần kiểm tra tiến trình thực tế trên hệ điều hành (ví dụ: `Get-Process`) hoặc truy vấn tài khoản thực tế (`check_account.py`) thay vì chỉ tin tưởng vào sự tồn tại của cửa sổ dòng lệnh. Nên xây dựng cơ chế Heartbeat định kỳ.

* **Cấu hình tham số chốt lời (Take Profit Parameters):**
  * *Vấn đề:* Tham số `base_target` mặc định cho Forex đặt ở mức `180.0` ($180 USD cho 0.01 lot) đòi hỏi giá phải đi tới **1,800 pips** mới kích hoạt chốt lời. Đây là mức phi thực tế đối với giao dịch trong ngày, làm các lệnh bị giữ liên phiên vô thời hạn cho tới khi chạm mốc Hard Stop 24H.
  * *Bài học:* Phải điều chỉnh mục tiêu chốt lời tương thích với biên độ biến động tự nhiên (ATR) và khối lượng giao dịch của từng loại tài sản.

* **Ghi nhật ký hệ thống (Log Target Separation):**
  * *Vấn đề:* Các log thông tin khởi động và khôi phục lệnh (`log_info`) chỉ hiển thị trên console và không được ghi vào file `.jsonl` hằng ngày, làm mất dữ liệu chẩn đoán khi cửa sổ CMD bị tắt.
  * *Bài học:* Phải phân tách rõ ràng và lưu trữ các log vận hành quan trọng vào một file log hệ thống riêng biệt (ví dụ: `system.log`), không chỉ phụ thuộc vào hiển thị ở màn hình Console.

---

## 📅 2026-06-23 (Báo cáo đối soát & phân tích log tối tự động)

### 📊 TỔNG QUAN PHIÊN GIAO DỊCH
* **Số lệnh đã đóng**: 0 lệnh (Thắng: 0, Thua: 0)
* **Tổng P&L ròng**: +0.00 USD
* **Số tín hiệu bị ML Veto (Từ chối)**: 33 tín hiệu
* **Số tín hiệu bị chặn bởi Governor (Portfolio limits)**: 0 tín hiệu

### 🧠 BÀI HỌC KINH NGHIỆM ĐẮT GIÁ & PHÂN TÍCH LỆNH THUA
* **Không phát sinh lệnh thua lỗ hôm nay** hoặc hệ thống chưa đóng vị thế nào chịu lỗ. Đây là tín hiệu tốt thể hiện việc kiểm soát rủi ro của hệ thống hoạt động ổn định.

* **Phân tích các tín hiệu bị ML Veto**:
  * **USDJPY**: ML đã lọc bỏ `11` tín hiệu vào lệnh nguy hiểm do rủi ro thua lỗ dự báo vượt ngưỡng.
  * **NZDUSD**: ML đã lọc bỏ `11` tín hiệu vào lệnh nguy hiểm do rủi ro thua lỗ dự báo vượt ngưỡng.
  * **EURUSD**: ML đã lọc bỏ `5` tín hiệu vào lệnh nguy hiểm do rủi ro thua lỗ dự báo vượt ngưỡng.
  * **GBPUSD**: ML đã lọc bỏ `3` tín hiệu vào lệnh nguy hiểm do rủi ro thua lỗ dự báo vượt ngưỡng.
  * **AUDUSD**: ML đã lọc bỏ `3` tín hiệu vào lệnh nguy hiểm do rủi ro thua lỗ dự báo vượt ngưỡng.
  * *Bài học rút ra*: Bộ lọc ML đang bảo vệ tài khoản khỏi các biến động nhiễu. Tránh can thiệp thủ công vào các quyết định phủ quyết này.

---

## 📅 2026-06-24 (Báo cáo đối soát & phân tích log tối tự động)

### 📊 TỔNG QUAN PHIÊN GIAO DỊCH
* **Số lệnh đã đóng**: 0 lệnh (Thắng: 0, Thua: 0)
* **Tổng P&L ròng**: +0.00 USD
* **Số tín hiệu bị ML Veto (Từ chối)**: 7761 tín hiệu
* **Số tín hiệu bị chặn bởi Governor (Portfolio limits)**: 0 tín hiệu

### 🧠 BÀI HỌC KINH NGHIỆM ĐẮT GIÁ & PHÂN TÍCH LỆNH THUA
* **Không phát sinh lệnh thua lỗ hôm nay** hoặc hệ thống chưa đóng vị thế nào chịu lỗ. Đây là tín hiệu tốt thể hiện việc kiểm soát rủi ro của hệ thống hoạt động ổn định.

* **Phân tích các tín hiệu bị ML Veto**:
  * **BTCUSD**: ML đã lọc bỏ `1600` tín hiệu vào lệnh nguy hiểm do rủi ro thua lỗ dự báo vượt ngưỡng.
  * **XAUUSD**: ML đã lọc bỏ `2968` tín hiệu vào lệnh nguy hiểm do rủi ro thua lỗ dự báo vượt ngưỡng.
  * **US100**: ML đã lọc bỏ `2239` tín hiệu vào lệnh nguy hiểm do rủi ro thua lỗ dự báo vượt ngưỡng.
  * **US500**: ML đã lọc bỏ `48` tín hiệu vào lệnh nguy hiểm do rủi ro thua lỗ dự báo vượt ngưỡng.
  * **US30**: ML đã lọc bỏ `153` tín hiệu vào lệnh nguy hiểm do rủi ro thua lỗ dự báo vượt ngưỡng.
  * **EURUSD**: ML đã lọc bỏ `90` tín hiệu vào lệnh nguy hiểm do rủi ro thua lỗ dự báo vượt ngưỡng.
  * **GBPUSD**: ML đã lọc bỏ `346` tín hiệu vào lệnh nguy hiểm do rủi ro thua lỗ dự báo vượt ngưỡng.
  * **AUDUSD**: ML đã lọc bỏ `92` tín hiệu vào lệnh nguy hiểm do rủi ro thua lỗ dự báo vượt ngưỡng.
  * **NZDUSD**: ML đã lọc bỏ `200` tín hiệu vào lệnh nguy hiểm do rủi ro thua lỗ dự báo vượt ngưỡng.
  * **USDCHF**: ML đã lọc bỏ `11` tín hiệu vào lệnh nguy hiểm do rủi ro thua lỗ dự báo vượt ngưỡng.
  * **USDCAD**: ML đã lọc bỏ `14` tín hiệu vào lệnh nguy hiểm do rủi ro thua lỗ dự báo vượt ngưỡng.
  * *Bài học rút ra*: Bộ lọc ML đang bảo vệ tài khoản khỏi các biến động nhiễu. Tránh can thiệp thủ công vào các quyết định phủ quyết này.

---
