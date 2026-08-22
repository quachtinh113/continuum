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

---

## 10. Phản biện: DCA hay không DCA (kết hợp ML và chỉ báo)

### 10.1 Luận cứ CHỐNG DCA (bằng chứng)

**a) Giải phẫu theo chỉ báo — không bối cảnh nào cứu được DCA (4,418 lệnh, full12, không lọc):**

| Bối cảnh lúc vào lệnh | Bucket tốt nhất có DCA | PF |
|---|---|---|
| ADX (mọi dải 0→100) | ADX 30–40 | 0.33 |
| Phiên (5 phiên) | OVERLAP_ASIA_EU | 0.34 |
| Vol expansion (atr_ratio) | 1.1–1.3 | 0.29 |
| Thuận/ngược RSI_H4 | ngược H4 | 0.28 |
| Mã (10 mã) | US30 | 0.33 |
| ADX × phiên (9 tổ hợp) | ADX>25 × EUROPE | 0.43 |

→ Không có chỉ báo đơn nào biến DCA thành dương; bất kỳ "DCA có điều kiện chỉ báo" nào cũng chỉ hội tụ về "ít DCA hơn".

**b) Hình dạng rủi ro (elite6, stop 2.6, khác biệt duy nhất là DCA):**

| | Có DCA | Không DCA |
|---|---|---|
| Net 36m | +$2,604 | +$2,608 (**giống nhau**) |
| Avg loss | −$18.2 | −$14.6 |
| Skewness | −0.33 | +0.24 |
| p1 trade PnL | −$64 | −$40 |
| MC P(DD ≥ 10%) | **27.3%** | 12.7% |
| MC P(DD ≥ 15%) | 5.0% | 1.2% |

→ Ở config cũ, DCA **không thêm kỳ vọng, chỉ thêm đuôi trái**. Con số "chu kỳ DCA lỗ −$8.7k" ở mức trade phóng đại thiệt hại thật: cùng những chu kỳ bất lợi đó không DCA vẫn dính stop; khác biệt thật là variance.

### 10.2 Luận cứ BẢO VỆ DCA (bằng chứng — đây là phần bất ngờ)

Khi đặt DCA lên **config mới** (stop 2.2×ATR + session mask), kết quả đảo chiều:

| Config (elite6, stop 2.2, mask) | 36m Net | 36m DD | 36m Sharpe | Hold Net | Hold DD | Hold Sharpe | Hold Calmar |
|---|---|---|---|---|---|---|---|
| Không DCA | +$4,853 | **3.54%** | 2.17 | +$3,094 | **2.03%** | 3.09 | 15.3 |
| DCA tối đa 1 layer | +$5,404 | 4.54% | 2.16 | +$3,575 | 2.83% | 3.16 | 12.6 |
| DCA 2 layer (gốc) | +$5,976 | 5.53% | 2.24 | +$3,840 | 3.00% | 3.22 | 12.8 |
| **DCA 2 layer + ML-gate v2 (OOS, thr 0.45)** | **+$5,997** | 4.59% | **2.35** | **+$3,881** | 2.39% | **3.41** | **16.3** |

**Cơ chế giải thích nghịch lý:** với stop 2.6×ATR, layer 2 đặt tại 2.5×ATR — ngay sát stop → gần như luôn bị cắt với 3× exposure (avg layer-2 cycle: −$21.9). Với stop 2.2×ATR, layer 2 hiếm khi chạm tới (avg DCA giảm 0.22→0.15), DCA thực chất thành 1 layer tại 1.5×ATR; giá vào trung bình thấp hơn giúp chu kỳ bất lợi hồi về BE nhiều hơn. Chu kỳ DCA vẫn lỗ ở mức trade (layer 1: −$3.9, layer 2: −$18.2) nhưng **ít hơn phương án để base lot dính stop** → net danh mục cao hơn ~$1,100/36m.

**ML-gate làm được gì:** model v2 (AUC 0.59, quá yếu để làm veto vào lệnh) lại **đủ tốt để gác cổng DCA**: giữ nguyên lợi nhuận của DCA 2 layer (+$5,997) nhưng kéo DD về 4.59% (từ 5.53%) và holdout DD 2.39% (từ 3.00%) — Calmar 16.3, cao nhất mọi cấu hình. Lý do: quyết định DCA là quyết định "có tăng exposure vào vị thế đang lỗ không" — chi phí sai lầm lớn và bất đối xứng, nên ngay cả phân loại yếu cũng có giá trị; còn quyết định vào lệnh có chi phí sai lầm nhỏ (stop chặt) nên phân loại yếu chỉ cắt volume.

### 10.3 Phán quyết

1. **DCA nguyên bản (stop 2.6, 2 layer, không mask): BỎ** — return-neutral, risk-additive, P(DD≥10%) 27%.
2. **DCA trên nền config mới: GIỮ, có ML-gate** — config tốt nhất toàn cục: `stop 2.2 + mask + DCA 2 layer + ML-gate v2 @0.45`.
3. Nếu ưu tiên DD tối thiểu tuyệt đối (quỹ prop rule chặt): **Không DCA** vẫn là lựa chọn bảo thủ hợp lệ (DD 3.54%/2.03%), đổi ~20% lợi nhuận lấy ~1 điểm DD.
4. Bài học phương pháp: **một thành phần không tốt/xấu cố định — nó tốt/xấu trong tương tác với tham số khác**. Kết luận "DCA phá hủy" ở §2 đúng với config cũ và sai với config mới; chỉ backtest in-engine mới phát hiện được, phân tích trade-level không thể.

**Caveat:** ML-gate dùng model v2_oos (học 24 tháng đầu) → 12 tháng holdout là OOS thật; 24 tháng đầu của cửa sổ 36m là in-sample cho model. Ngưỡng 0.45 chọn từ sweep OOF, chưa tối ưu riêng cho DCA.

---

## 11. ML vs Không ML — đối chứng trên cùng nền config (elite6, no-DCA, stop 2.2, mask)

Định nghĩa 3 chế độ:
- **Không ML (thuần chỉ báo):** không veto vào lệnh, không quyết định ML ở mốc 12h (chỉ stop 2.2×ATR, trailing BE, 24h hard cut), sizing không điều chỉnh theo ML.
- **ML v1 (live hiện tại):** model thoái hóa → thực chất = time-stop 12h cố định + sizing ×0.7 mọi lệnh.
- **ML v2 (OOS-clean):** model thật (AUC 0.59) làm veto vào lệnh @0.50 + quyết định 12h.

| Chế độ | 36m Net | 36m PF | 36m DD | 36m Sharpe | Hold Net | Hold PF | Hold DD | Hold Sharpe |
|---|---|---|---|---|---|---|---|---|
| **Không ML** | **+$6,361** | **1.24** | 5.70% | **2.32** | **+$4,794** | **1.49** | 3.91% | **4.10** |
| ML v1 (live) | +$4,853 | 1.21 | **3.54%** | 2.17 | +$3,094 | 1.35 | **2.03%** | 3.09 |
| ML v2 | +$3,150 | 1.13 | 6.08% | 1.56 | +$843 | 1.09 | 7.58% | 1.04 |

**Đọc kết quả:**
1. **Thuần chỉ báo thắng về lợi nhuận & Sharpe trên cả hai cửa sổ** (+31% net 36m, +55% net holdout so với ML v1). Cơ chế: bỏ cut 12h cố định → lệnh giữ trung bình 11.5h thay vì 10h, để trailing BE và 24h hard cut làm việc; bỏ sizing ×0.7 → lot đúng risk budget.
2. **ML v1 có một giá trị thật: giảm DD** (3.54% vs 5.70%; 2.03% vs 3.91%) — vì cut 12h hoạt động như "time-stop" hạn chế thời gian phơi nhiễm. Nhưng đó là time-stop, không phải ML; có thể tái tạo bằng quy tắc cố định không cần model.
3. **ML v2 làm veto vào lệnh là tệ nhất** — nhất quán với §3: AUC 0.59 quá yếu, cắt volume ở regime đang lãi, và khi cắm vào quyết định 12h thì phá vỡ hành vi đã tinh chỉnh.
4. Kết hợp với §10: ML v2 **có giá trị ở đúng một chỗ — gác cổng DCA** (quyết định bất đối xứng, chi phí sai lầm lớn). → Kiến trúc ML hợp lý: **ML không quyết định vào/ra lệnh; ML chỉ quyết định có tăng exposure hay không.**

---

## 12. Xếp hạng toàn bộ cấu hình & Con đường tối ưu

Tất cả chạy trên elite6, stop 2.2×ATR, session mask (trừ dòng đầu = live cũ).

| # | Cấu hình | 36m Net | 36m DD | 36m Sharpe | Hold Net | Hold DD | Hold Sharpe | Hold Calmar |
|---|---|---|---|---|---|---|---|---|
| 0 | Live cũ (ML v1, DCA 2, stop 2.6, không mask) | +$2,604 | 10.66% | 1.15 | +$2,363 | 7.33% | 2.19 | 3.2 |
| 1 | ML v2 veto + no-DCA | +$3,150 | 6.08% | 1.56 | +$843 | 7.58% | 1.04 | 1.1 |
| 2 | ML v1 + no-DCA | +$4,853 | **3.54%** | 2.17 | +$3,094 | **2.03%** | 3.09 | 15.3 |
| 3 | ML v1 + DCA 2 + ML-gate | +$5,997 | 4.59% | 2.35 | +$3,881 | 2.39% | 3.41 | 16.3 |
| 4 | Không ML + no-DCA | +$6,361 | 5.70% | 2.32 | +$4,794 | 3.91% | 4.10 | 12.3 |
| **5** | **HYBRID: Không ML vào/ra + DCA 2 + ML-gate DCA** | **+$7,966 (+79.7%)** | 5.26% | **2.54** | **+$5,642 (+56.4%/yr)** | 3.97% | **4.29** | 14.2 |

**Hồ sơ sống sót HYBRID (36m):** 4/4 năm dương (+$296 / +$1,495 / +$2,128 / +$4,047), 29/37 tháng lãi, tháng xấu nhất −$546, underwater dài nhất 181 ngày. Monte Carlo 5,000: 100% có lãi, final p5 $15,347 / median $17,972, MaxDD p99 = 10.3%, P(DD≥10%) = 1.2%, P(DD≥15%) = 0%. Holdout: 11/13 tháng lãi, tháng xấu nhất −$51, PF 1.54.

**Rủi ro tập trung giảm:** 36m theo mã — XAUUSD +$3,130, BTCUSD +$2,467, USDJPY +$1,186, US30 +$1,106, AUDUSD +$78, NZDUSD −$4. Năm mã dương thay vì hai.

### Con đường tối ưu (kết luận của toàn bộ nghiên cứu)

```
KIẾN TRÚC:
  Vào lệnh  : thuần chỉ báo (OU/Kalman Á · SMC-HMM Âu · KAMA+ADX Mỹ), KHÔNG ML veto
  Ra lệnh   : stop 2.2×ATR(H1) · trailing BE · 24h hard cut — KHÔNG cut 12h bằng ML
  Sizing    : fixed-fractional theo ATR, KHÔNG điều chỉnh theo ML score
  DCA       : tối đa 2 layer (1.5 / 2.5 ×ATR), chỉ khi ML-gate v2 cho phép (loss-prob ≤ 0.45)
  Phiên     : session mask (AUDUSD ∉ US; NZDUSD ∉ EU,US; US30 ∉ OVERLAP_EU_US)
  Universe  : 6 Elite (AUDUSD, NZDUSD, USDJPY, XAUUSD, US30, BTCUSD)

NGUYÊN TẮC RÚT RA:
  1. ML không nên quyết định vào/ra lệnh khi AUC < 0.65 — nó chỉ cắt volume ở regime đang lãi.
  2. ML có giá trị ở quyết định BẤT ĐỐI XỨNG: "có tăng exposure vào vị thế đang lỗ không".
  3. Tham số không tốt/xấu tuyệt đối: DCA phá hủy với stop 2.6, sinh lời với stop 2.2.
  4. Mọi "edge" từ thống kê trade-level phải qua backtest in-engine (slot tái phân bổ).
```

**Caveat cuối:** (i) cấu hình được chọn qua nhiều vòng thí nghiệm trên cùng 36m dữ liệu → rủi ro selection bias tích lũy; holdout 12 tháng chỉ "mù" với model v2_oos, không mù với lựa chọn tham số. (ii) Khuyến nghị triển khai theo bậc: demo 4 tuần → live risk 50% → full risk; dừng nếu DD live vượt 6% (≈ p95 Monte Carlo). (iii) Fill mô phỏng close M15 + slippage ước lượng; live có thể kém 10–20%.

---

## 13. Nhật ký triển khai HYBRID lên live (2026-08-22)

| Hạng mục | Thay đổi | File |
|---|---|---|
| Stop | 2.6 → **2.2×ATR** (`SOFT_ATR_MULTIPLIER`) | `config/settings.py`, `main.py` |
| ML veto vào lệnh | **TẮT** (`ML_ENTRY_VETO_ACTIVE=False`) | `main.py` |
| SOFT_ML_SL (M5 risk exit) | **TẮT** — exit này chưa từng được backtest; với v1≈0.89>0.70 nó đóng gần như mọi lệnh sớm → nghi phạm chính khiến live kém backtest | `main.py` |
| ML 12h cut/extend | **TẮT**; 24h hard cut giữ | `main.py` |
| ML sizing ×0.7/×1.5 | **TẮT** (`ML_SIZING_ACTIVE=False`) | `main.py` |
| DCA | tối đa **2 layer** (từ 3, parity backtest) + **ML-gate** `gatekeeper_dca_v2.json` @0.45, fail-safe: lỗi gate → không DCA | `main.py`, `src/ml/dca_gate.py` |
| Session mask | đã áp dụng từ trước | — |

**Kiểm chứng trước restart:** parity feature live-vs-backtest sai số median ≤0.16% (30 lệnh mẫu), pytest 144/144 pass, gate end-to-end trên MT5 thật cho xác suất 0.38–0.61 (US30 veto, còn lại pass).

**Sự cố phát hiện:** bot và launcher đã chết ~8h trước khi triển khai (heartbeat cũ 28,428s) — launcher `start_bot.bat` không còn process. Đã khởi động lại qua launcher (có vòng auto-restart). Bot mới PID 7448, heartbeat tươi. Sổ lệnh trống lúc restart.

**Lưu ý vận hành:** (1) `pytest` ghi fixture giả (EURUSD ticket 111/222) vào `logs/audit_*.jsonl` thật — cần tách audit path cho test. (2) Mọi flag HYBRID có thể rollback qua env (`ML_ENTRY_VETO_ACTIVE=true`, `SOFT_ATR_MULTIPLIER=2.6`, …) không cần sửa code. (3) Kế hoạch: theo dõi 4 tuần; ngưỡng dừng DD live 6%; retrain gate model hằng quý từ `training_data.csv` bằng `scripts/train_gatekeeper_v2.py`.

---

## 14. Kiểm tra pipeline live: lấy dữ liệu → chỉ báo → regime → khối alpha → Governor (2026-08-22 03:01 UTC, thứ Bảy)

Công cụ: `scratch/trace_alpha_pipeline.py` — chạy đúng các hàm của bot (`MT5Connector.get_rates`, `V9ContinuumBot.evaluate_symbol_signal`, `PortfolioGovernor.process_token_queue/evaluate_risk_matrix`) ở chế độ read-only, song song với bot live.

| Tầng | Kết quả | Đánh giá |
|---|---|---|
| Kết nối MT5 | connect OK, account 206539306, balance $878.20, 2 model nạp (v1 + DCA-gate 23 feature) | ✅ |
| Dữ liệu 6 mã × M15/H1/H4 | 100 bar/khung, 0 NaN, latency 0–36 ms; FX/vàng/US30 bar đóng cuối cách 376–421 phút (đóng cửa thứ Sáu), BTC tươi 1 phút; gaps H4=3 (cuối tuần), XAU/US30 H1 gaps=4 (rollover hằng ngày) | ✅ đúng kỳ vọng cuối tuần |
| Phiên & mask | session=ASIA, is_weekend=True; mask mở cho cả 6 mã lúc 03h UTC | ✅ |
| Khối alpha | Chạy 0–16 ms/mã; tạo 2 tín hiệu (XAUUSD BUY, BTCUSD SELL), 4 HOLD | ✅ chạy; ⚠️ xem lỗi dưới |
| Governor | Queue 2 token → winner XAUUSD BUY; risk matrix approved | ✅ |
| Bot live | heartbeat 4 s, 0 lỗi; 0 bản ghi audit vì `is_weekend` → standby (đúng thiết kế) | ✅ |

### ⚠️ Lỗi thiết kế trong khối alpha phiên Á: Kalman Z-score không bất biến theo đơn vị giá

`KalmanFilterTracker(q=1e-4, r=1e-2)` dùng phương sai **tuyệt đối theo đơn vị giá**. Sau khi hội tụ, `sqrt(p+r) = 0.1046` cho **mọi** tài sản, nên `z = (close − ước lượng) / 0.1046`:

| Mã | Biến động M15 cuối | z-score | Hệ quả |
|---|---|---|---|
| AUDUSD | 0.00008 | −0.00 | **không bao giờ** vượt ±2 → phiên Á chết hẳn (0 lệnh ASIA trong 36m) |
| NZDUSD | 0.00019 | −0.00 | như trên |
| USDJPY | 0.003 | −0.03 | gần như chết (chỉ fire khi nến ≥0.21 JPY) |
| XAUUSD | 4.01 | **−95.8** | fire với **bất kỳ** nến nào > $0.21 |
| US30 | 9 | +207 | như trên (chỉ còn OU theta>0 làm bộ lọc) |
| BTCUSD | 5.8 | **+3,430** | như trên |

Thực chất "Asia Mean-Reversion" hiện là: **FX = tắt; vàng/BTC/US30 = fade nến M15 vừa đóng** (nến đỏ → BUY, nến xanh → SELL), chỉ lọc bởi OU θ>0. Backtest dùng cùng tracker/cùng tham số nên **mọi con số đã kiểm chứng đều đã bao gồm hành vi này** — cấu hình HYBRID vẫn hợp lệ, nhưng khối alpha không làm điều nó tuyên bố. Ghi nhận BTC ASIA là phân khúc lãi lớn nhất (+$1,163/36m) — tức bản "lỗi" này đang sinh lời; **không hot-fix trên live**; muốn sửa (chuẩn hóa z theo ATR hoặc log-return) phải qua backtest 36m + holdout như mọi thay đổi khác.

### ⚠️ Phát hiện thứ hai: giới hạn spread không được thực thi

`SPREAD_LIMIT_FX/INDEX/GOLD/CRYPTO` (5/50/50/100) được định nghĩa trong `settings.py` và gắn vào `SymbolSpec.spread_limit`, nhưng **không có chỗ nào chặn lệnh** khi spread vượt ngưỡng — spread chỉ tham gia công thức chấm điểm Governor `ADX×0.7 − spread×0.3`. Lúc trace (cuối tuần): US30 spread 130 > 50, BTC 1000 > 100 mà tín hiệu vẫn đi tới Governor và được approve. Ngày thường spread hẹp nên ít ảnh hưởng, nhưng tại rollover 21–22 UTC / tin tức, bot có thể vào lệnh với chi phí gấp 3–5 lần bình thường. Đề xuất: thêm hard-gate `spread > spec.spread_limit → skip` ngay trong `process_signals` (thay đổi nhỏ, có thể backtest bằng mô hình spread rollover sẵn có của engine).

---

## 15. Spread thật, lỗi đơn vị của Governor, và kiểm tra lại toàn hệ thống

### 15.1 Live audit 10–22/08 (trước HYBRID): hai mã mạnh nhất gần như không giao dịch

| Mã | ROUTE | VETOED (ML v1) | BLOCKED (Governor) | Lý do chính |
|---|---|---|---|---|
| XAUUSD | 12,323 | 9,643 | 4,002 | — |
| BTCUSD | **0** | 0 | 256 | 100% "USD factor concentration exceeded" |
| US30 | **0** | 417 | 0 | 100% ML veto v1 (đã gỡ trong HYBRID) |
| USDJPY | 11 | 1,505 | 57 | ML veto v1 |
| AUDUSD | 29 | 490 | 169 | ML veto v1 + USD factor |

`is_usd_symbol()` = `"USD" in symbol or startswith("US")` → **cả 6 mã elite đều là "USD"** → `max_usd_exposure=2` thực chất là trần 2 vị thế toàn danh mục; BTC (tín hiệu phiên Á) luôn đến sau khi 2 slot đã bị chiếm.

### 15.2 Spread thật từng nến thay mô hình 1/3/20/80 pip

Spread median thực (pip): AUD 0.9 · NZD 1.7 · JPY 1.0 · XAU 17.9 · **US30 260** · **BTC 2,160** (p95 rollover: FX 8–14, XAU 60). Mô hình cũ: crypto/index = **1.5 pip** — sai hàng nghìn lần cho BTC. Ngưỡng `SPREAD_LIMIT` cố định cũng sai hiệu chuẩn (BTC limit 2,000 < median) → gate cố định sẽ giết BTC; gate phải **tương đối** (k × median 100 nến).

### 15.3 Tách bạch "chi phí thật" và "méo lựa chọn" (holdout 12m, HYBRID)

| Cấu hình | Chi phí | Governor chấm điểm | Net | PF | DD | Sharpe |
|---|---|---|---|---|---|---|
| HYBRID (§12) | mô hình | mô hình | +$5,642 | 1.54 | 3.97% | 4.29 |
| `rs_base` | **thật** | **pip thô thật** | +$2,384 | 1.18 | 4.70% | 2.05 |
| `gov_model` | thật | mô hình (hằng số theo lớp tài sản) | **+$5,023** | **1.48** | 4.33% | **4.01** |
| `gov_atr` | thật | % ATR (unit-free) | +$4,109 | 1.36 | 5.26% | 3.44 |

→ Thuần chi phí thật: −$619 (−11%). **Lỗi đơn vị của Governor**: −$2,640 — công thức `ADX×0.7 − spread×0.3` với pip thô làm BTC (2,160 pip) không bao giờ thắng cạnh tranh slot. **Live đang chạy đúng lỗi này** (tick spread pip thô) → giải thích BTC 0 lệnh ở §15.1 cùng với quy tắc USD-factor.

### 15.4 Kiểm chứng từng điều chỉnh trên nền đã sửa (chi phí thật + Governor chấm theo lớp tài sản)

| Biến thể | Hold Net | Hold DD | Hold Sharpe | 36m Net | 36m DD | 36m Sharpe | Phán quyết |
|---|---|---|---|---|---|---|---|
| Nền: HYBRID + Governor class | +$5,023 | 4.33% | 4.01 | +$5,716 | **6.15%** | 2.11 | ✅ chuẩn mới |
| + Spread gate k=3 (tương đối) | ≈ +$24 | = | = | (đang chạy tổ hợp) | | | ✅ bảo hiểm rẻ, trung tính |
| + Kalman adaptive **toàn bộ** (nền thô) | −$806 vs nền thô | 5.98% | 1.56 | ≈ nền thô | 9.79% | 0.65 | ❌ |
| + Kalman adaptive **chỉ FX** | **+$5,493** | 4.47% | **4.39** | +$4,861 | **12.49%** | 1.83 | ❌ holdout tốt hơn nhưng 36m DD **gấp đôi** |
| + USD-factor chỉ đếm FX | +$3,917 | 4.09% | 2.99 | (nền thô: PF 1.05, DD 13.5%) | | | ❌ trần 2 vị thế đồng thời là bộ hạn chế variance có ích |
| Governor chấm theo %ATR | +$4,109 | 5.26% | 3.44 | +$3,798 | 12.53% | 1.50 | ❌ kém hằng số lớp tài sản |

**Kết luận mục 1 & 2 (yêu cầu ban đầu):**
- **Mục 1 — spread gate:** chấp nhận dạng **tương đối** (k=3 × median 100 nến); ngưỡng cố định `SPREAD_LIMIT_*` bị bác vì sai hiệu chuẩn. Giá trị thực của mục này không nằm ở gate mà ở phát hiện kéo theo: **lỗi đơn vị trong chấm điểm Governor** (−$2,640 holdout, BTC 0 lệnh live 2 tuần).
- **Mục 2 — Kalman:** lỗi đơn vị là thật, nhưng cả hai cách sửa đều **làm xấu hồ sơ rủi ro 36m**. Hành vi "fade nến" của vàng/BTC và "phiên Á tắt" của FX — dù không phải thiết kế — là phần đã được kiểm chứng sinh lời. **Giữ nguyên `fixed`**, ghi nhận là "hành vi hiệu dụng" thay vì "Kalman mean-reversion". Code adaptive giữ lại sau flag để nghiên cứu tiếp (ví dụ: chỉ bật khi đã có ≥6 tháng live dữ liệu FX phiên Á).

**Lưu ý parity:** live `evaluate_symbol_signal` dùng `rates_m15` **có nến đang hình thành** làm điểm cuối, backtest dùng nến đã đóng — khác biệt có sẵn từ trước ở mọi phiên, chưa định lượng; nên đồng bộ trong vòng tinh chỉnh sau.
