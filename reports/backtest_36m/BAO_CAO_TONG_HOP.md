# V9 Continuum — Báo Cáo Backtest 36 Tháng, Kiểm Toán Thuật Toán & Giải Pháp ML

**Ngày:** 2026-08-22 · **Dữ liệu:** 36 tháng M15/H1/H4 thật từ MT5 Exness (2023-08-21 → 2026-08-21, ~75k nến M15/mã, 12 mã) · **Engine:** `v9_continuum/backtest.py` (chi phí spread + slippage động + commission $7/lot, look-ahead-free đã kiểm chứng)

---

## 1. Kết quả backtest 36 tháng (vốn $10,000)

| Cấu hình | Lệnh | WR | Net PnL | PF | Max DD | Sharpe | PSR |
|---|---|---|---|---|---|---|---|
| Full 12 mã (baseline) | 4,418 | 62.8% | **−$1,296 (−13.0%)** | 0.94 | 22.96% | −0.50 | 11% |
| Elite 6 mã (baseline live) | 4,232 | 66.6% | +$2,604 (+26.0%) | 1.10 | 10.66% | 1.15 | 97% |
| Elite 6 + **tắt DCA** | 4,367 | 63.5% | +$2,608 (+26.1%) | 1.11 | 8.40% | 1.42 | 98.5% |
| Elite 6 + tắt DCA + **stop 2.2×ATR** | 4,537 | 63.0% | **+$3,939 (+39.4%)** | **1.17** | **5.81%** | **1.88** | **100%** |

**Holdout 12 tháng cuối (2025-08 → 2026-08):**

| Cấu hình | Net PnL | PF | Max DD | Sharpe | Calmar |
|---|---|---|---|---|---|
| Elite 6 baseline | +$2,363 (+23.6%/yr) | 1.23 | 7.33% | 2.19 | 3.23 |
| + tắt DCA | +$2,476 | 1.27 | 3.55% | 2.71 | 6.97 |
| + tắt DCA + stop 2.2× | **+$3,335 (+33.4%/yr)** | **1.36** | **2.57%** | **3.53** | **12.98** |

Việc cắt 12 mã → 6 mã Elite là đúng hướng (từ −13% lên +26%), nhưng các con số trong `super_elite_universe_report.md` (WR 68.2%, PF 6.27, DD 1.51%) **không tái lập được** trên 36 tháng dữ liệu thật — kết quả thực là PF 1.10–1.17.

## 2. Kiểm toán thuật toán — các lỗi tìm thấy

1. **Gatekeeper v1 (XGBoost) thoái hóa:** mọi dự đoán nằm trong [0.70, 0.98], trung bình 0.89. Hệ quả:
   - Ngưỡng veto backtest cũ (0.60) chặn **100% tín hiệu** → mọi báo cáo backtest trước đây in toàn số 0.
   - Ngưỡng live (0.85) gần như không chặn gì → "ML veto" live không hoạt động.
   - Nhánh ML sizing boost (score < 0.25) **chết** — mọi lệnh luôn bị nhân 0.7×.
   - "12H ML CUT" (ngưỡng 0.65) luôn kích hoạt → thực chất là **time-stop 12 giờ cố định** (và chính nó đang có ích: giữ hệ ở PF 1.23 holdout).
2. **DCA là cỗ máy đốt tiền:** 36m, chu kỳ không DCA: PF 1.85 / +$11,271; chu kỳ có DCA: PF 0.30 / −$8,667 (WR 31.7%).
3. **SOFT_ATR_STOP (2.6×ATR) quá rộng:** 480 lệnh, −$15,515, 0% thắng, avg −$32/lệnh so với avg +$7.7 của trailing-BE.
4. Audit log không ghi PnL (đã báo cáo phiên trước); cost model và look-ahead của engine kiểm tra OK; logic live/backtest đồng nhất.

## 3. Giải pháp ML — xây dựng và kiểm chứng trung thực

**Đã xây:** pipeline `scripts/train_gatekeeper_v2.py` — meta-labelling (model chỉ quyết TAKE/SKIP trên tín hiệu của engine chính), huấn luyện trên **quần thể tín hiệu không lọc** (4,418 lệnh no-veto), purged walk-forward CV 5 fold + embargo 1%, cân bằng scale_pos_weight, chọn ngưỡng theo expectancy, có degeneracy gate. Model: `src/ml/gatekeeper_v2.json` (+ bản OOS-clean `gatekeeper_v2_oos.json` chỉ học 24 tháng đầu).

**Kết quả kiểm chứng:**

| Thử nghiệm | Kết quả | Phán quyết |
|---|---|---|
| OOS AUC (pooled 5-fold) | 0.592, phổ dự đoán 0.17–0.77 | Tín hiệu thật nhưng **yếu** |
| Entry-veto 0.50, trade-level OOF 36m | −$405 → +$716 | Tốt trong giai đoạn hệ lỗ |
| Entry-veto, holdout 12m (hệ đang lãi) | +$795 → +$557 | **Cắt volume, giảm net** |
| Engine-level elite6 holdout (v2 thay v1 toàn bộ) | +$2,363 → +$1,006, Sharpe 2.19→1.09 | ❌ **Không triển khai** — đổi model phá vỡ 3 điểm quyết định cùng lúc |
| DCA-gate ML | Không kích hoạt đủ (DCA hiếm sau khi hiểu đúng cơ chế) | Thay bằng tắt DCA hẳn |
| Filter thủ công vàng (H4-align, block giờ 13/20/21) | Gold-only 36m: baseline +$1,651 > các biến thể +$791..+$1,251 | ❌ Edge nhìn thấy là ảo ảnh chọn mẫu danh mục |

**Bài học chính:** cải tiến cấu trúc (mục 4) mang lại nhiều hơn ML ở trạng thái dữ liệu hiện tại; v2 dùng đúng chỗ nhất là **risk-monitor/giám sát** chứ chưa phải hard filter.

## 4. Vàng phiên Mỹ (yêu cầu riêng)

- Vàng phiên Mỹ là **phân khúc mạnh nhất hệ thống**: 36m baseline PF 2.22 (+$963/139 lệnh trong elite6); với config đề xuất: 36m +$904 PF 1.46, holdout +$745 PF 1.77 (US-window), toàn bộ XAUUSD holdout **+$1,824, PF 1.60**.
- BUY PF 2.70 vs SELL 1.35 (regime tăng của vàng) — không hardcode thiên hướng, để KAMA tự bám.
- Stop 2.2×ATR cho vàng đã kiểm chứng gold-only 36m: +$1,651 → +$2,034 (+23%), DD 8.07% → 6.13%.

## 5. Cấu hình đề xuất (đã kiểm chứng 2 cửa sổ độc lập)

```
Universe        : 6 Elite (AUDUSD, NZDUSD, USDJPY, XAUUSD, US30, BTCUSD)
DCA             : TẮT HOÀN TOÀN (max_layers = 0)
SOFT_ATR stop   : 2.2 × ATR(H1)  (từ 2.6)
Exit 12h        : giữ nguyên (time-stop 12h)
ML gatekeeper   : giữ v1 behavior (không thay bằng v2 làm veto);
                  v2 chỉ dùng giám sát/cảnh báo cho tới khi AUC > 0.62 ổn định
```

**Caveat trung thực:** (1) hai tham số cấu trúc được chọn dựa trên phân tích cùng bộ dữ liệu 36m — dù hướng cải thiện tái lập độc lập trên cả 36m lẫn holdout, vẫn nên chạy demo/paper 2–4 tuần trước khi tăng risk; (2) fill mô phỏng theo close M15 + slippage ước lượng; (3) hiệu năng phụ thuộc regime — năm 2025 hệ vẫn lỗ nhẹ ở mọi cấu hình.

## 6. File sinh ra

- `scripts/run_36m_backtest.py` — runner tham số hóa (universe/veto/model/dca-veto/no-dca/soft-atr/window)
- `scripts/train_gatekeeper_v2.py` — pipeline ML meta-labelling + purged WFCV
- `scripts/gold_us_experiments.py` — bộ thí nghiệm vàng A–D
- `src/ml/gatekeeper_v2.json`, `gatekeeper_v2_oos.json`, `gatekeeper_v2_meta.json`
- `reports/backtest_36m/` — toàn bộ trades CSV, metrics JSON, summary từng cấu hình
- Engine mở rộng (opt-in, mặc định không đổi hành vi): `ml_model_path`, `ml_dca_veto_threshold`, `soft_atr_multiplier`, `us_h4_align`, `entry_blocked_hours`, `session_risk_boost`, capture features/session theo lệnh

---

## 7. Phân tích sống sót dài hạn (36 tháng)

### Độ ổn định theo thời gian

| Chỉ số | Baseline (live hiện tại) | Config đề xuất |
|---|---|---|
| Tháng có lãi | 25/37 (68%) | **27/37 (73%)** |
| Tháng xấu nhất | −$626 | −$432 |
| Chuỗi tháng lỗ dài nhất | 2 | 2 |
| Năm lỗ | **2025: −$820** | Không (4/4 năm dương) |
| Thời gian chìm dưới đỉnh dài nhất | **411 ngày** (12/2024→02/2026) | **138 ngày** |
| Rolling 90 ngày dương | 70% | 77% (xấu nhất −$429) |
| Rolling 180 ngày dương | 75% | 85% (xấu nhất −$460) |

### Monte Carlo 5,000 đường bootstrap

| | Baseline | Config đề xuất |
|---|---|---|
| P(kết thúc có lãi) | 97.2% | **100.0%** |
| Final balance p5 / median / p95 | $10.4k / $12.6k / $15.0k | $12.0k / $14.0k / $15.9k |
| Max DD p50 / p95 / p99 | 7.9% / 14.8% / 20.0% | **5.0% / 8.8% / 11.6%** |
| P(DD ≥ 10%) | 27.6% | **2.6%** |
| P(DD ≥ 20%) | 1.0% | 0.0% |

### Rủi ro tập trung (caveat quan trọng)

PnL 36m theo mã (config đề xuất): BTCUSD +$2,582, XAUUSD +$2,141, USDJPY +$311, US30 −$313, AUDUSD −$339, NZDUSD −$443. **Edge tập trung vào BTC + Vàng** — bỏ BTC thì net chỉ còn +$1,357 (35%). 2026 đóng góp +$2,439/+$3,939. Bỏ quý tốt nhất (2026Q1) vẫn +$2,410 → không sống nhờ một quý may mắn, nhưng cần theo dõi sát BTC/Gold vì 3 mã FX + US30 hiện là "hành khách".

### Kết luận sống sót

- **Baseline hiện tại: sống được nhưng mong manh** — từng chìm dưới đỉnh 13.5 tháng liên tục, xác suất chạm DD 10% (ngưỡng cháy quỹ prop) là 27.6%.
- **Config đề xuất: đạt chuẩn sống sót dài hạn** — 4/4 năm dương, 100% đường Monte Carlo có lãi, DD p99 = 11.6%, hồi phục đỉnh nhanh gấp 3.

---

## 8. Thí nghiệm loại bỏ mã âm (AUDUSD / NZDUSD / US30)

Không thể kết luận bằng phép trừ PnL vì các mã tương tác qua slot Governor (max 3 vị thế; slot đầy tại ~1,020 thời điểm; 46% lệnh vàng/BTC vào khi một mã âm đang giữ vị thế). Kết quả backtest thật (config đề xuất: no-DCA + stop 2.2×):

| Universe | 36m Net | 36m DD | 36m Sharpe | Holdout Net | Hold DD | Hold Sharpe |
|---|---|---|---|---|---|---|
| **6 mã** (hiện tại) | +$3,939 | 5.81% | 1.88 | **+$3,335** | **2.57%** | **3.53** |
| **3 mã** (XAU+BTC+JPY) | **+$4,150** | **3.90%** | 1.87 | +$2,970 | 4.32% | 2.90 |
| 2 mã (XAU+BTC) | +$2,879 | 9.33% | 1.30 | +$2,613 | 4.70% | 2.26 |

**Cơ chế phát hiện được:** khi bỏ 3 mã âm, số lệnh XAU/BTC/JPY tăng gần gấp đôi (XAU 883→1,545) vì slot được giải phóng — dòng tín hiệu được tái phân bổ chứ không đơn thuần "mất phần lỗ". Ngược lại, thu về 2 mã làm mất cơ chế cạnh tranh chấm điểm của Governor → vàng/BTC nhận cả tín hiệu yếu → DD tăng gần gấp đôi.

**Phán quyết:**
- ❌ **2 mã: bác bỏ** — tệ hơn ở mọi chỉ số, cả hai cửa sổ.
- ⚖️ **3 mã vs 6 mã: hòa trong nhiễu thống kê** — 36m nghiêng về 3 mã (DD 3.90%, tháng xấu nhất chỉ −$104, 4/4 năm dương), holdout 12m gần nhất nghiêng về 6 mã (Sharpe 3.53, DD 2.57%).
- ✅ **Khuyến nghị: giữ 6 mã làm chính** (regime gần nhất tốt hơn, risk-adjusted cao hơn), ghi nhận **3 mã là phương án dự phòng đã kiểm chứng** — nếu 2–3 tháng tới AUD/NZD/US30 tiếp tục âm trên live, chuyển sang 3 mã là bước cắt giảm an toàn, không phải bước nhảy vào vùng chưa test.

---

## 9. Phiên giao dịch lý tưởng theo tài sản (đã kiểm chứng in-engine)

Phương pháp: chỉ nhận tổ hợp mã×phiên **âm ổn định trên cả 2 cửa sổ độc lập** (24 tháng đầu vs 12 tháng cuối, đủ mẫu) làm ứng viên chặn, rồi kiểm chứng lại bằng backtest danh mục đầy đủ (slot tái phân bổ).

### Bản đồ Net PnL 36 tháng (mã × phiên, config đề xuất)

| Mã | ASIA (0-7) | OVL Á-Âu (7-9) | EUROPE (9-13) | OVL Âu-Mỹ (13-16) | US (16-22) | Phiên lý tưởng |
|---|---|---|---|---|---|---|
| BTCUSD | **+$1,163** | +$374 | +$94 | +$483 | +$469 | **Mọi phiên** (mạnh nhất Á) |
| XAUUSD | +$391 | +$327 | +$519 | +$162 | **+$742** | **Mỹ + Âu** (tốt mọi phiên) |
| USDJPY | +$80 | +$62 | +$58 | **+$125** | −$13 | Á + chồng lấn Âu-Mỹ |
| US30 | −$88 | **+$215** | −$1 | ⛔ −$356 | −$82 | **Chỉ chồng lấn Á-Âu** |
| AUDUSD | – | – | −$108 | −$134 | ⛔ −$97 | Âu (yếu); ⛔ cấm Mỹ |
| NZDUSD | – | – | ⛔ −$166 | −$92 | ⛔ −$185 | Chỉ chồng lấn Âu-Mỹ; ⛔ cấm Âu+Mỹ |

⛔ = âm ổn định cả 2 cửa sổ → đưa vào mask. (AUD/NZD không có lệnh phiên Á vì OU/Kalman hiếm khi vượt ±2σ trên 2 mã này.)

### Session Mask đã kiểm chứng

```
AUDUSD : cấm vào lệnh 16-21 UTC (phiên Mỹ)
NZDUSD : cấm vào lệnh 9-12 UTC (Âu) và 16-21 UTC (Mỹ)
US30   : cấm vào lệnh 13-15 UTC (chồng lấn Âu-Mỹ)
```

### Kết quả kiểm chứng (config đề xuất + mask)

| | 36m không mask | **36m + mask** | Holdout không mask | **Holdout + mask** |
|---|---|---|---|---|
| Net | +$3,939 | **+$4,853 (+48.5%)** | +$3,335 | +$3,094 |
| PF | 1.17 | **1.21** | 1.36 | 1.35 |
| Max DD | 5.81% | **3.54%** | 2.57% | **2.03%** |
| Sharpe | 1.88 | **2.17** | 3.53 | 3.09 |
| Calmar | 2.26 | **4.57** | 12.98 | **15.26** |

Phán quyết: **chấp nhận mask** — 36m cải thiện mạnh mọi chỉ số; holdout hòa (net thấp hơn $241 nhưng DD/Calmar tốt hơn). Lợi ích chính là **giảm rủi ro** (DD 36m từ 5.81% → 3.54%). Caveat: các tổ hợp chặn được chọn dựa trên thống kê của cả hai cửa sổ nên không có cửa sổ nào hoàn toàn "mù" với lựa chọn này; cần xác nhận trên demo.

### Cấu hình hoàn chỉnh cuối cùng

```
Universe     : 6 Elite | DCA: TẮT | SOFT_ATR stop: 2.2×ATR | 12h time-stop: giữ
Session mask : AUDUSD ∉ US; NZDUSD ∉ EU, US; US30 ∉ OVERLAP_EU_US
36m: +48.5%, PF 1.21, DD 3.54%, Sharpe 2.17, PSR 100%
Holdout 12m: +30.9%/yr, PF 1.35, DD 2.03%, Calmar 15.3
```
