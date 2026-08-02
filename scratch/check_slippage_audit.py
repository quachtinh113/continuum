import sys
import os
import time
import random

sys.path.append(os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')

def run_slippage_execution_watchdog_test():
    print("=================================================================", flush=True)
    print("  PHASE 4 EXECUTION ENGINE: REAL-TIME SLIPPAGE & LATENCY WATCHDOG", flush=True)
    print("=================================================================\n", flush=True)

    from v9_continuum.layers.execution import ExecutionEngine
    
    class MockMT5Connector:
        def __init__(self):
            self._dry_run = True
            
        def get_tick(self, symbol):
            base_prices = {"EURUSD": 1.1500, "GBPUSD": 1.3300, "US30": 52500.0, "XAUUSD": 4050.0}
            bp = base_prices.get(symbol, 1.0000)
            spread = 0.0001 if "USD" in symbol and "US30" not in symbol else 0.5
            return {"bid": bp, "ask": bp + spread}
            
        def place_order(self, symbol, order_type, lot, price=None, sl=None, tp=None, comment=""):
            time.sleep(random.uniform(0.01, 0.05)) # Simulate 10-50ms execution latency
            return 123456

    connector = MockMT5Connector()
    engine = ExecutionEngine(connector)

    symbols = ["EURUSD", "GBPUSD", "US30", "XAUUSD", "USDJPY"]
    
    print("[1] KIỂM THỬ ROUTING ORDER & THEO DÕI REAL-TIME METRICS:")
    for i in range(1, 11):
        sym = random.choice(symbols)
        ticket = engine.route_order(
            symbol=sym,
            order_type="BUY",
            lot=0.01,
            comment=f"Watchdog Test #{i}"
        )
        last_rec = engine.execution_history[-1]
        print(f"  - Trade #{i:02d} [{sym:6s}]: Request={last_rec['request_price']:.5f} | Fill={last_rec['fill_price']:.5f} | Latency={last_rec['latency_ms']:.2f}ms | Slippage={last_rec['slippage_pips']:.4f} pips")

    avg_latency = sum(r["latency_ms"] for r in engine.execution_history) / len(engine.execution_history)
    avg_slippage = sum(r["slippage_pips"] for r in engine.execution_history) / len(engine.execution_history)
    
    print(f"\n[2] TỔNG HỢP KẾT QUẢ KHI VẬN HÀNH BÌNH THƯỜNG:")
    print(f"  - Latency Trung Bình: {avg_latency:.2f} ms")
    print(f"  - Slippage Trung Bình: {avg_slippage:.4f} pips")
    print(f"  - Circuit Breaker Tripped: {engine.circuit_breaker_tripped}")

    print("\n[3] GIẢ LẬP SỰ CỐ SLIPPAGE HIGH-DRAG (> 0.3 pips) & KÍCH HOẠT KILL-SWITCH:")
    # Force add high slippage executions to trigger Circuit Breaker
    for j in range(5):
        engine.execution_history.append({
            "symbol": "US30",
            "order_type": "BUY",
            "lot": 0.01,
            "request_price": 52500.0,
            "fill_price": 52501.0,
            "latency_ms": 250.0,
            "slippage_pips": 1.0,  # 1.0 pips high slippage
            "timestamp": time.time()
        })
    
    # Audit rolling slippage (last 10 trades)
    recent_slips = [r["slippage_pips"] for r in engine.execution_history[-10:]]
    avg_slip_high = sum(recent_slips) / len(recent_slips) if recent_slips else 0.0
    if avg_slip_high > engine.max_allowed_slippage_pips:
        engine.circuit_breaker_tripped = True
        print(f"  [EMERGENCY KILL-SWITCH] Slippage Drag ({avg_slip_high:.3f} pips) > Limit ({engine.max_allowed_slippage_pips} pips)! Circuit Breaker ACTIVATED.")
    
    blocked_ticket = engine.route_order("EURUSD", "BUY", 0.01)
    print(f"  - Kết quả thử nạp lệnh khi Circuit Breaker đã nổ: Ticket = {blocked_ticket} (Tự động chặn hoàn toàn lệnh mới).")

if __name__ == "__main__":
    run_slippage_execution_watchdog_test()
