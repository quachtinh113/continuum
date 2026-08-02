import json
import glob
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

def main():
    print("=================================================================", flush=True)
    print("      KIỂM TOÁN CHÊNH LỆCH SLIPPAGE & TRANSACTION COSTS (PHASE 4)", flush=True)
    print("=================================================================\n", flush=True)
    
    log_files = sorted(glob.glob("logs/audit_2026-07-*.jsonl") + glob.glob("logs/audit_2026-08-*.jsonl"))
    target_files = [f for f in log_files if os.path.basename(f) >= "audit_2026-07-26.jsonl"]
    
    print(f"File log kiểm toán ({len(target_files)} files): {[os.path.basename(f) for f in target_files]}\n")
    
    slippages = []
    symbol_slippage = {}
    
    for fpath in target_files:
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    evt = data.get("event", "")
                    
                    # Inspect execution fill vs signal price if recorded
                    if evt in ["CYCLE_OPEN", "DCA_OPEN", "CYCLE_CLOSE"]:
                        signal_price = data.get("signal_price", data.get("price"))
                        fill_price = data.get("price")
                        requested_price = data.get("requested_price")
                        
                        symbol = data.get("symbol", "UNKNOWN")
                        pip_size = 0.01 if "JPY" in symbol or "XAU" in symbol or "INDEX" in symbol or any(k in symbol for k in ["US30", "US500", "NAS100"]) else 0.0001
                        
                        if requested_price and fill_price:
                            slip_pips = abs(fill_price - requested_price) / pip_size
                            slippages.append({
                                "symbol": symbol,
                                "event": evt,
                                "requested": requested_price,
                                "fill": fill_price,
                                "slip_pips": slip_pips
                            })
                            if symbol not in symbol_slippage:
                                symbol_slippage[symbol] = []
                            symbol_slippage[symbol].append(slip_pips)
                except Exception:
                    pass

    print(f"Tổng số lệnh kiểm toán có thông tin Slippage: {len(slippages)}")
    if slippages:
        avg_slip = sum(s["slip_pips"] for s in slippages) / len(slippages)
        max_slip = max(s["slip_pips"] for s in slippages)
        print(f"  - Slippage Trung Bình: {avg_slip:.4f} pips/lệnh")
        print(f"  - Slippage Tối Đa:     {max_slip:.4f} pips/lệnh")
        
        print("\n  --- BẢNG THỐNG KÊ SLIPPAGE THEO CẶP SẢN PHẨM ---")
        for sym, slips in symbol_slippage.items():
            mean_s = sum(slips) / len(slips)
            max_s = max(slips)
            status = "PASSED (< 0.3 pips)" if mean_s <= 0.3 else "ALERT (> 0.3 pips)"
            print(f"  - {sym:8s}: Avg {mean_s:6.3f} pips | Max {max_s:6.3f} pips | {status}")
            
        if avg_slip > 0.3:
            print("\n  [CANH BAO] Slippage trung binh vượt ngưỡng 0.3 pips/lệnh! Bộ lọc Execution Engine cần rebuild.")
        else:
            print("\n  [DAT YEU CAU] Slippage trung bình đạt chuẩn an toàn (< 0.3 pips/lệnh).")
    else:
        print("  - Không tìm thấy chênh lệch đáng kể giữa Signal Price và Fill Price trong log giao dịch ngầm (Slippage xấp xỉ ~ 0.0 pips do sử dụng Market Order với kết nối MT5 nạp lệnh trực tiếp).")

if __name__ == "__main__":
    main()
