import os
import json
from datetime import datetime, timezone
from pathlib import Path

def main(custom_date=None):
    """
    Parses today's audit log file and appends lessons learned to lessons_learned.md.
    """
    project_root = Path(__file__).resolve().parent.parent
    
    # Determine target date
    if custom_date:
        target_date = custom_date
    else:
        target_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
    audit_file = project_root / "logs" / f"audit_{target_date}.jsonl"
    lessons_file = project_root / "lessons_learned.md"
    
    print(f"Reading audit log: {audit_file}")
    
    closed_trades = []
    vetoed_signals = []
    blocked_signals = []
    
    if audit_file.exists():
        try:
            with open(audit_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                        event = record.get("event")
                        risk_decision = record.get("risk_decision")
                        
                        if event == "CYCLE_CLOSE":
                            closed_trades.append(record)
                        elif risk_decision == "VETOED":
                            vetoed_signals.append(record)
                        elif risk_decision == "BLOCKED":
                            blocked_signals.append(record)
                    except Exception as e:
                        print(f"Warning: failed to parse JSON line: {e}")
        except Exception as e:
            print(f"Error reading audit file: {e}")
    else:
        print("Audit log file does not exist for today.")

    # Calculate statistics
    total_closed = len(closed_trades)
    wins = [t for t in closed_trades if t.get("profit_usd", 0) > 0]
    losses = [t for t in closed_trades if t.get("profit_usd", 0) <= 0]
    total_net_pnl = sum(t.get("profit_usd", 0) for t in closed_trades)
    
    total_vetoed = len(vetoed_signals)
    total_blocked = len(blocked_signals)
    
    # ── Render Markdown Summary ──
    summary_md = f"\n## 📅 {target_date} (Báo cáo đối soát & phân tích log tối tự động)\n\n"
    summary_md += "### 📊 TỔNG QUAN PHIÊN GIAO DỊCH\n"
    summary_md += f"* **Số lệnh đã đóng**: {total_closed} lệnh (Thắng: {len(wins)}, Thua: {len(losses)})\n"
    summary_md += f"* **Tổng P&L ròng**: {total_net_pnl:+.2f} USD\n"
    summary_md += f"* **Số tín hiệu bị ML Veto (Từ chối)**: {total_vetoed} tín hiệu\n"
    summary_md += f"* **Số tín hiệu bị chặn bởi Governor (Portfolio limits)**: {total_blocked} tín hiệu\n\n"
    
    summary_md += "### 🧠 BÀI HỌC KINH NGHIỆM ĐẮT GIÁ & PHÂN TÍCH LỆNH THUA\n"
    
    if losses:
        summary_md += "* **Chi tiết lệnh thua lỗ phát sinh hôm nay**:\n"
        for t in losses:
            symbol = t.get("symbol", "N/A")
            direction = t.get("direction", "N/A")
            profit = t.get("profit_usd", 0.0)
            reason = t.get("reason", "N/A")
            price = t.get("price", 0.0)
            summary_md += f"  * **{symbol} ({direction})**: Thua lỗ {profit:.2f} USD. Lý do đóng: `{reason}`. Giá đóng: `{price}`.\n"
            summary_md += f"    * *Bài học rút ra*: Cần kiểm tra xem hành vi giá tại `{price}` có đi ngược lại mô hình xu hướng lớn KAMA/ADX hay do biến động tức thời (noise) kích hoạt thời gian cắt giảm 12H.\n"
    else:
        summary_md += "* **Không phát sinh lệnh thua lỗ hôm nay** hoặc hệ thống chưa đóng vị thế nào chịu lỗ. Đây là tín hiệu tốt thể hiện việc kiểm soát rủi ro của hệ thống hoạt động ổn định.\n"
        
    if vetoed_signals:
        summary_md += "\n* **Phân tích các tín hiệu bị ML Veto**:\n"
        # Group by symbol
        veto_counts = {}
        for v in vetoed_signals:
            sym = v.get("symbol", "N/A")
            veto_counts[sym] = veto_counts.get(sym, 0) + 1
            
        for sym, count in veto_counts.items():
            summary_md += f"  * **{sym}**: ML đã lọc bỏ `{count}` tín hiệu vào lệnh nguy hiểm do rủi ro thua lỗ dự báo vượt ngưỡng.\n"
        summary_md += "  * *Bài học rút ra*: Bộ lọc ML đang bảo vệ tài khoản khỏi các biến động nhiễu. Tránh can thiệp thủ công vào các quyết định phủ quyết này.\n"
        
    if blocked_signals:
        summary_md += "\n* **Phân tích các lệnh bị Governor chặn**:\n"
        blocked_reasons = {}
        for b in blocked_signals:
            reason = b.get("reason", "N/A")
            blocked_reasons[reason] = blocked_reasons.get(reason, 0) + 1
        for reason, count in blocked_reasons.items():
            summary_md += f"  * Bị chặn do `{reason}`: `{count}` lần.\n"
        summary_md += "  * *Bài học rút ra*: Các quy định giới hạn tiếp xúc USD và giới hạn Combo Vàng & Chỉ số đang hoạt động đúng như thiết kế để tránh tập trung rủi ro.\n"
        
    summary_md += "\n---\n"
    
    # Write or append to lessons_learned.md
    if lessons_file.exists():
        try:
            content = lessons_file.read_text(encoding="utf-8")
            # Check if this date already has an entry to avoid duplicates
            if f"## 📅 {target_date}" in content:
                print(f"Summary for {target_date} already exists in lessons_learned.md. Skipping append.")
                return
            
            with open(lessons_file, "a", encoding="utf-8") as f:
                f.write(summary_md)
            print(f"Successfully appended today's summary to {lessons_file}")
        except Exception as e:
            print(f"Error appending to lessons file: {e}")
    else:
        try:
            lessons_file.write_text(summary_md, encoding="utf-8")
            print(f"Created lessons file and wrote today's summary: {lessons_file}")
        except Exception as e:
            print(f"Error creating lessons file: {e}")

if __name__ == "__main__":
    main()
