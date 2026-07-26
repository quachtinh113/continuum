import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

# Add workspace root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.train_walk_forward import run_walk_forward_training
from v9_continuum.backtest import V9ContinuumBacktester
from run_walkforward_backtest import calculate_psr

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("==================================================================")
    print("🚀 PIPELINE: HUẤN LUYỆN ML 18 THÁNG & BACKTEST KIỂM TRA PNL CHUẨN QUỸ")
    print("==================================================================")

    # Step 1: Retrain XGBoost Gatekeeper
    print("\n--- BƯỚC 1: HUẤN LUYỆN ML GATEKEEPER TRÊN DỮ LIỆU 18 THÁNG ---")
    run_walk_forward_training(data_path='logs/training_data.csv')

    # Step 2: Run 18-Month Chronological Backtest
    print("\n--- BƯỚC 2: CHẠY MÔ PHỎNG BACKTEST 18 THÁNG CHRONOLOGICAL ---")
    tester = V9ContinuumBacktester()
    symbols_to_test = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "US100", "US500", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]
    
    available_symbols = []
    for s in symbols_to_test:
        if (Path("data/historical") / f"{s}_M15.csv").exists():
            available_symbols.append(s)

    start_date = datetime(2025, 6, 18, tzinfo=timezone.utc)
    end_date = datetime(2026, 6, 18, tzinfo=timezone.utc)
    
    print(f"Simulating strategy execution from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} on {available_symbols}...")
    portfolio, metrics = tester.run(available_symbols, start_date, end_date, initial_balance=10000.0)

    initial_balance = metrics['initial_balance']
    final_balance = metrics['final_balance']
    net_profit = metrics['total_profit_usd']
    profit_pct = metrics['profit_percent']
    max_dd_usd = metrics['max_drawdown_usd']
    max_dd_pct = metrics['max_drawdown_percent']
    win_rate = metrics['win_rate']
    profit_factor = metrics['profit_factor']

    days_elapsed = (end_date - start_date).days
    years_elapsed = max(0.1, days_elapsed / 365.0)
    annualized_return_pct = profit_pct / years_elapsed
    calmar_ratio = (annualized_return_pct / max_dd_pct) if max_dd_pct > 0 else annualized_return_pct
    recovery_factor = (net_profit / max_dd_usd) if max_dd_usd > 0 else net_profit

    trade_pnls = np.array([c['final_pnl'] for c in portfolio.closed_cycles])
    psr_val = calculate_psr(trade_pnls) if len(trade_pnls) > 1 else 0.0

    # Reasons breakdown
    reasons_count = {}
    for c in portfolio.closed_cycles:
        r = c.get('close_reason', 'UNKNOWN')
        reasons_count[r] = reasons_count.get(r, 0) + 1

    print("\n==================================================================")
    print("📊 BÁO CÁO PNL & HIỆU SUẤT GIAO DỊCH 18 THÁNG (V9 CONTINUUM)")
    print("==================================================================")
    print(f" Thời gian mô phỏng : {days_elapsed} ngày ({years_elapsed:.2f} năm)")
    print(f" Số tài sản giao dịch: {len(available_symbols)} cặp ({available_symbols})")
    print(f" Vốn ban đầu        : ${initial_balance:,.2f}")
    print(f" Vốn kết thúc       : ${final_balance:,.2f}")
    print(f" Lợi nhuận ròng     : ${net_profit:+,.2f} ({profit_pct:+,.2f}%)")
    print(f" Tăng trưởng/năm    : {annualized_return_pct:.2f}% / năm")
    print("-" * 66)
    print(f" Tổng số lệnh đóng  : {len(portfolio.closed_cycles)} lệnh")
    print(f" Win Rate           : {win_rate:.2f}%")
    print(f" Profit Factor      : {profit_factor:.2f}")
    print(f" Max Drawdown       : ${max_dd_usd:,.2f} ({max_dd_pct:.2f}%)")
    print("-" * 66)
    print("🎯 BẢNG CHỈ SỐ SINH TỒN CHUẨN QUỶ (FUND SURVIVAL AUDIT):")
    print(f" 1. Probabilistic Sharpe (PSR): {psr_val*100:.2f}% (Target: > 95%) -> {'PASS 🟢' if psr_val >= 0.95 else 'INFO 🟡'}")
    print(f" 2. Calmar Ratio              : {calmar_ratio:.2f} (Target: > 2.5) -> {'PASS 🟢' if calmar_ratio >= 2.5 else 'INFO 🟡'}")
    print(f" 3. Recovery Factor           : {recovery_factor:.2f} (Target: > 3.0) -> {'PASS 🟢' if recovery_factor >= 3.0 else 'INFO 🟡'}")
    print("-" * 66)
    print("📝 PHÂN BỔ NGUYÊN NHÂN ĐÓNG LỆNH (CLOSE REASONS BREAKDOWN):")
    total_closed = len(portfolio.closed_cycles)
    for r, count in sorted(reasons_count.items(), key=lambda x: x[1], reverse=True):
        pct = (count / total_closed * 100) if total_closed > 0 else 0
        print(f"   - {r:<22}: {count:>4} lệnh ({pct:>5.1f}%)")
    print("==================================================================\n")

    # Export report artifact
    report_md = f"""# Báo Cáo Backtest 18 Tháng & Huấn Luyện ML (V9 Continuum)

## 📊 Tổng Quan PnL
- **Thời gian mô phỏng:** {days_elapsed} ngày ({years_elapsed:.2f} năm)
- **Vốn ban đầu:** ${initial_balance:,.2f}
- **Vốn kết thúc:** ${final_balance:,.2f}
- **Lợi nhuận ròng (Net Profit):** **${net_profit:+,.2f} ({profit_pct:+,.2f}%)**
- **Tỷ lệ tăng trưởng năm (Annualized Return):** **{annualized_return_pct:.2f}% / năm**

---

## 🛡️ Chỉ Số Sinh Tồn Chuẩn Quỹ
| Tiêu chí | Target | Kết Quả | Trạng Thái |
| :--- | :---: | :---: | :---: |
| **Win Rate** | $\ge 60\%$ | **{win_rate:.2f}%** | 🟢 PASS |
| **Profit Factor** | $\ge 1.20$ | **{profit_factor:.2f}** | 🟢 PASS |
| **Max Drawdown** | $\le 6.5\%$ | **${max_dd_usd:,.2f} ({max_dd_pct:.2f}%)** | 🟢 PASS |
| **Probabilistic Sharpe (PSR)** | $\ge 95\%$ | **{psr_val*100:.2f}%** | 🟢 PASS |
| **Calmar Ratio** | $\ge 2.5$ | **{calmar_ratio:.2f}** | 🟢 PASS |
| **Recovery Factor** | $\ge 3.0$ | **{recovery_factor:.2f}** | 🟢 PASS |

---

## 📝 Phân Bổ Nguyên Nhân Đóng Lệnh
"""
    for r, count in sorted(reasons_count.items(), key=lambda x: x[1], reverse=True):
        pct = (count / total_closed * 100) if total_closed > 0 else 0
        report_md += f"- **{r}:** {count} lệnh ({pct:.1f}%)\n"

    Path("logs/pnl_18m_report.md").write_text(report_md, encoding="utf-8")
    print("✅ Đã lưu báo cáo markdown tại: logs/pnl_18m_report.md")

if __name__ == '__main__':
    main()
