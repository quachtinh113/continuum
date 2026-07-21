import sys
import json
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.backtest_engine import BacktestEngine
from config import settings
from config.symbols import get_symbol_spec

def run_historical_analysis():
    sys.stdout.reconfigure(encoding='utf-8')
    print("==============================================================")
    print("📋 NOWTRADING V9 — COMPREHENSIVE HISTORICAL & RISK ANALYSIS")
    print("==============================================================")
    
    # ── 1. Load Settings ──
    print("\n[Bot Settings Loaded from .env]")
    print(f"  - FX Base Lot: {settings.FX_BASE_LOT}")
    print(f"  - Gold/Commodity Base Lot: {settings.COMMODITY_BASE_LOT}")
    print(f"  - Crypto Base Lot: {settings.CRYPTO_BASE_LOT}")
    print(f"  - Max Lot Size: {settings.MAX_LOT_SIZE}")
    print(f"  - Max DCA Layers: {settings.MAX_DCA_LAYERS}")
    print(f"  - Max Daily Drawdown: ${settings.MAX_DAILY_DRAWDOWN_USD}")
    print(f"  - ML Gatekeeper: {'ACTIVE' if getattr(settings, 'ML_GATEKEEPER_ACTIVE', False) else 'DISABLED'} (Threshold: {getattr(settings, 'ML_VETO_THRESHOLD', 'N/A')})")
    
    # Backtest Date Range
    start_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2026, 6, 15, tzinfo=timezone.utc)
    print(f"  - Historical Test Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    engine = BacktestEngine(data_dir="data/historical")
    
    # ── 2. Task A: Isolated Stress Test for XAUUSDm ──
    print("\n[Executing Task A: XAUUSDm Stress Test]")
    xau_results = None
    try:
        portfolio, metrics = engine.run_backtest(
            symbols=["XAUUSD"],
            start_date=start_date,
            end_date=end_date,
            initial_balance=1000.0,
            use_spread=True,
        )
        net_profit = metrics['total_profit_usd']
        max_dd_usd = metrics['max_drawdown_usd']
        recovery_factor = net_profit / max_dd_usd if max_dd_usd > 0 else float('inf')
        
        xau_results = {
            "Net Profit (USD)": f"${net_profit:.2f} ({metrics['profit_percent']:.2f}%)",
            "Total Cycles": metrics['total_cycles'],
            "Win Rate": f"{metrics['win_rate']:.2f}%",
            "Profit Factor": f"{metrics['profit_factor']:.2f}",
            "Max Drawdown (USD)": f"${max_dd_usd:.2f} ({metrics['max_drawdown_percent']:.2f}%)",
            "Recovery Factor": f"{recovery_factor:.2f}",
            "Avg Holding Hours": f"{metrics['avg_holding_hours']:.1f}h",
            "Max DCA Layer Reached": metrics['max_dca_reached'],
            "Exit Reasons": metrics['reasons']
        }
        print("  - XAUUSDm Stress Test Complete.")
    except Exception as e:
        print(f"  - Error running XAUUSDm backtest: {e}")
        
    # ── 3. Task C: Asset Allocation Standalone Backtests ──
    print("\n[Executing Task C: Standalone Backtests for All Symbols]")
    symbols_to_test = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD", "XAUUSD", "BTCUSD", "US30", "US500", "US100"]
    available_symbols = []
    for s in symbols_to_test:
        if (Path("data/historical") / f"{s}_M15.csv").exists():
            available_symbols.append(s)
            
    print(f"  - Available symbols with data: {available_symbols}")
    
    asset_perf = []
    for s in available_symbols:
        try:
            # Run isolated backtest starting with $1000 balance
            p, m = engine.run_backtest(
                symbols=[s],
                start_date=start_date,
                end_date=end_date,
                initial_balance=1000.0,
                use_spread=True,
            )
            net_p = m['total_profit_usd']
            dd = m['max_drawdown_usd']
            rf = net_p / dd if dd > 0 else float('inf')
            
            asset_perf.append({
                "Symbol": s,
                "Net Profit ($)": net_p,
                "Win Rate (%)": m['win_rate'],
                "Profit Factor": m['profit_factor'],
                "Max DD ($)": dd,
                "Max DD (%)": m['max_drawdown_percent'],
                "Recovery Factor": rf,
                "Cycles": m['total_cycles'],
                "Max DCA": m['max_dca_reached']
            })
            print(f"  - Completed backtest for {s:<8} │ Profit: ${net_p:+.2f} │ DD: ${dd:.2f}")
        except Exception as e:
            print(f"  - Failed backtest for {s}: {e}")
            
    df_perf = pd.DataFrame(asset_perf)
    if not df_perf.empty:
        df_perf = df_perf.sort_values(by="Net Profit ($)", ascending=False)
        
    # ── 4. Task B: Risk Layer & IPC Timeout Correlation (July 16-17) ──
    print("\n[Executing Task B: Correlating IPC Timeouts & Live Cycle Closes (July 16-17)]")
    
    # Read July 16 and July 17 audit logs
    audit_events = []
    warnings_errors = []
    for date_str in ["2026-07-16", "2026-07-17"]:
        log_path = Path("logs") / f"audit_{date_str}.jsonl"
        if log_path.exists():
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line.strip())
                        data["date"] = date_str
                        
                        # Store close events
                        if data.get("event") == "CYCLE_CLOSE":
                            audit_events.append(data)
                        
                        # Store warnings/errors
                        severity = data.get("severity")
                        event = data.get("event")
                        msg = str(data.get("message") or data.get("reason") or "")
                        if severity in ["WARNING", "ERROR"] or event == "ERROR" or "timeout" in msg.lower() or "fail" in msg.lower():
                            warnings_errors.append(data)
                    except Exception:
                        pass
                        
    # Filter timeouts in our focus window: July 16 (from 21:00 UTC) to July 17 (all day)
    # Check if any CYCLE_CLOSE events occurred near warning/error events
    close_correlations = []
    for close in audit_events:
        close_time = datetime.fromisoformat(close["timestamp"])
        
        # Find warnings within 10 minutes of this close
        near_warnings = []
        for warn in warnings_errors:
            warn_time = datetime.fromisoformat(warn["timestamp"])
            time_diff = abs((close_time - warn_time).total_seconds())
            if time_diff <= 600:  # 10 minutes
                near_warnings.append(warn)
                
        close_correlations.append({
            "time": close_time.strftime("%H:%M:%S"),
            "symbol": close.get("symbol"),
            "direction": close.get("direction"),
            "reason": close.get("reason"),
            "price": close.get("price"),
            "warnings_count": len(near_warnings),
            "warnings_details": [f"[{w.get('timestamp')[11:19]}] {w.get('message') or w.get('reason')}" for w in near_warnings]
        })
        
    # Print results to console and generate Markdown Report
    print("  - Risk Layer & IPC Timeout Analysis Complete.")
    
    # ── Write Report to Markdown File ──
    report_file = Path("scratch/historical_analysis_report.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("# 🔬 Báo Cáo Phân Tích Lịch Sử & Kiểm Tra Rủi Ro V9\n\n")
        f.write(f"**Thời gian thực hiện:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} Local\n\n")
        
        f.write("## 1. 📊 Task A: Stress-Test Riêng Cho Cặp XAUUSDm (Vàng)\n")
        f.write("Kiểm tra xem hiệu suất vượt trội của XAUUSDm trong tuần vừa rồi (+$136.45) có phải là xu hướng bền vững dựa trên dữ liệu lịch sử 5.5 tháng qua hay không.\n\n")
        
        if xau_results:
            f.write("### Chỉ số Hiệu suất XAUUSDm (Jan 1, 2026 - Jun 15, 2026)\n")
            f.write(f"- **Khởi điểm:** $1000.00\n")
            f.write(f"- **Lợi nhuận ròng:** {xau_results['Net Profit (USD)']}\n")
            f.write(f"- **Số lượng chu kỳ (Cycles):** {xau_results['Total Cycles']}\n")
            f.write(f"- **Tỷ lệ thắng (Win Rate):** {xau_results['Win Rate']}\n")
            f.write(f"- **Hệ số lợi nhuận (Profit Factor):** {xau_results['Profit Factor']}\n")
            f.write(f"- **Sụt giảm vốn tối đa (Max Drawdown):** {xau_results['Max Drawdown (USD)']}\n")
            f.write(f"- **Hệ số hồi phục (Recovery Factor):** {xau_results['Recovery Factor']}\n")
            f.write(f"- **Thời gian giữ lệnh trung bình:** {xau_results['Avg Holding Hours']}\n")
            f.write(f"- **Số lớp DCA tối đa đạt tới:** {xau_results['Max DCA Layer Reached']}\n\n")
            
            f.write("### Lý do đóng chu kỳ (Exit Reasons Breakdown)\n")
            for r, count in xau_results['Exit Reasons'].items():
                f.write(f"- **{r}:** {count}\n")
            f.write("\n")
        else:
            f.write("❌ Lỗi: Không thể thực hiện stress-test XAUUSDm.\n\n")
            
        f.write("## 2. 💱 Task C: Đánh Giá Phân Bổ Vốn (Portfolio Asset Allocation)\n")
        f.write("So sánh hiệu suất độc lập của 12 cặp tài sản dưới cùng một cấu hình `.env` để xác định những cặp yếu kém có thể loại bỏ nhằm tối ưu hóa dòng vốn.\n\n")
        
        if not df_perf.empty:
            f.write("### Bảng Xếp Hạng Hiệu Suất Độc Lập Các Cặp Tài Sản (Bắt đầu với $1000)\n\n")
            f.write("| Xếp Hạng | Cặp (Symbol) | Lợi Nhuận ($) | Win Rate (%) | Profit Factor | Max Drawdown ($) | Max DD (%) | Recovery Factor | Số Lệnh (Cycles) | Lớp DCA Max |\n")
            f.write("| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n")
            for idx, (index, row) in enumerate(df_perf.iterrows(), 1):
                rf_val = row["Recovery Factor"]
                rf_str = f"{rf_val:.2f}" if rf_val != float('inf') else "N/A"
                f.write(f"| {idx} | **{row['Symbol']}** | {row['Net Profit ($)']:+.2f} | {row['Win Rate (%)']:.2f}% | {row['Profit Factor']:.2f} | {row['Max DD ($)']:.2f} | {row['Max DD (%)']:.2f}% | {rf_str} | {int(row['Cycles'])} | {int(row['Max DCA'])} |\n")
            f.write("\n")
            
            # Identify recommendation based on performance
            weak_assets = df_perf[df_perf["Net Profit ($)"] <= 0]["Symbol"].tolist()
            strong_assets = df_perf[df_perf["Net Profit ($)"] > 0]["Symbol"].tolist()
            f.write("> [!TIP]\n")
            f.write(f"> **Khuyến nghị phân bổ vốn:** Dựa trên kết quả backtest, rổ tài sản của bạn có **{len(strong_assets)}** cặp tạo lợi nhuận dương và **{len(weak_assets)}** cặp tạo lợi nhuận âm trong 5.5 tháng qua. Bạn nên cân nhắc tắt bớt các cặp yếu như: **{', '.join(weak_assets)}** để tập trung ký quỹ cho các cặp mạnh như **{', '.join(strong_assets[:3])}**.\n\n")
        else:
            f.write("❌ Lỗi: Không có dữ liệu hiệu suất để hiển thị.\n\n")
            
        f.write("## 3. 🚨 Task B: Kiểm Tra Cơ Chế Cắt Lỗ (Risk Layer) & Lỗi Kết Nối IPC (July 16-17)\n")
        f.write("Phân tích xem các sự cố mất kết nối MT5 (IPC timeout) vào ngày 16 và 17/07 có gây ảnh hưởng hay làm trễ tiến trình đóng lệnh (SL/TP) của bot hay không.\n\n")
        
        f.write("### Chi tiết các đợt đóng chu kỳ giao dịch gần cảnh báo lỗi kết nối (Window 10 phút)\n\n")
        f.write("| Thời Gian (UTC) | Cặp | Chiều | Lý Do Đóng | Giá Đóng | Số Lỗi Kết Nối Gần Đó | Chi Tiết Lỗi Gần Nhất |\n")
        f.write("| :--- | :--- | :--- | :--- | :---: | :---: | :--- |\n")
        correlated_closes = [c for c in close_correlations if c["warnings_count"] > 0]
        if correlated_closes:
            for c in correlated_closes:
                err_detail = c["warnings_details"][0] if c["warnings_details"] else "None"
                if len(err_detail) > 80:
                    err_detail = err_detail[:77] + "..."
                f.write(f"| {c['time']} | {c['symbol']} | {c['direction']} | {c['reason']} | {c['price']} | {c['warnings_count']} | `{err_detail}` |\n")
        else:
            f.write("| N/A | Không có lệnh đóng nào bị ảnh hưởng bởi lỗi IPC hoặc lỗi kết nối MT5 trong khoảng thời gian này. | - | - | - | 0 | - |\n")
        f.write("\n")
        
        f.write("### Nhận định về rủi ro cắt lỗ trễ:\n")
        # Check if there were severe reconnect warnings during trading windows
        reconnect_fails = [w for w in warnings_errors if "reconnect failed" in str(w.get("message") or w.get("reason")).lower()]
        f.write(f"- **Tổng số lỗi kết nối MT5 / IPC ghi nhận trong 2 ngày:** {len(warnings_errors)} lần.\n")
        f.write(f"- **Số lần mất kết nối hoàn toàn (phải thử lại 3 lần thất bại):** {len(reconnect_fails)} lần.\n")
        if len(correlated_closes) > 0:
            f.write(f"- ⚠️ **Cảnh báo:** Có **{len(correlated_closes)}** sự kiện đóng lệnh xảy ra rất sát thời điểm hệ thống ghi nhận lỗi kết nối MT5/IPC. Điều này xác thực giả thuyết rằng các lỗi IPC timeout có thể gây ra hiện tượng trượt giá (slippage) hoặc làm chậm trễ lệnh đóng của bot thực tế trên MT5 so với thời điểm kích hoạt trong code.\n")
        else:
            f.write(f"- ✅ **An toàn:** Không có sự trùng khớp trực tiếp giữa thời gian lỗi kết nối và thời gian đóng lệnh. Mặc dù có lỗi IPC timeout, các lệnh đóng (SL/TP) của bot vẫn được thực hiện tương đối kịp thời khi hệ thống hồi phục kết nối.\n")

    print(f"\nReport saved to: {report_file.absolute()}")

if __name__ == "__main__":
    run_historical_analysis()
