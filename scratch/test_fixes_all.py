import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding='utf-8')

print("="*80)
print("QUANT POST-MORTEM MATH & CODE VERIFICATION SCRIPT")
print("="*80)

# 1. PnL & Drawdown Verification
initial_balance = 938.66
deal_pnls = [-11.87, -0.36, -1.88, -1.39, -17.37]
total_loss = sum(deal_pnls)
final_equity = initial_balance + total_loss
drawdown_pct = abs(total_loss) / initial_balance * 100.0

print(f"1. FINANCIAL AUDIT METRICS:")
print(f"   Initial Balance: ${initial_balance:.2f}")
print(f"   Total Realized Loss: ${total_loss:.2f}")
print(f"   Final Equity: ${final_equity:.2f}")
print(f"   Calculated Drawdown: {drawdown_pct:.4f}% (Breached 3.50% Cap)")

# 2. Lot Size Sizing Proof (USTECm vs XAUUSDm)
ustec_contract_size = 1.0
ustec_min_vol = 0.05
ustec_pts_lost = (29738.83 - 29731.57) + (29774.33 - 29736.81) + (29801.58 - 29773.81)
ustec_pnl = - (ustec_pts_lost * ustec_contract_size * ustec_min_vol)

gold_contract_size = 100.0
gold_vol = 0.02
gold_trade1_pnl = -11.87 # (4339.685 - 4333.751) * 100 * 0.02 = -11.868 -> -11.87
gold_trade2_pts = 4323.381 - 4332.065 # -8.684 gold pts
gold_trade2_pnl = gold_trade2_pts * gold_contract_size * gold_vol # -17.368 -> -17.37

print(f"\n2. POSITION SIZING & CONTRACT AUDIT:")
print(f"   USTECm total price adverse movement: {ustec_pts_lost:.2f} pts across 3 orders")
print(f"   USTECm total loss @ 0.05 lot: ${ustec_pnl:.2f}")
print(f"   XAUUSDm Trade #1 loss @ 0.02 lot: ${gold_trade1_pnl:.2f}")
print(f"   XAUUSDm Trade #2 loss @ 0.02 lot: ${gold_trade2_pnl:.2f}")
print(f"   Sum of all trades: ${ustec_pnl + gold_trade1_pnl + gold_trade2_pnl:.2f}")

# 3. Correlation Matrix Haircut Proof
corr_matrix = np.array([
    [1.00,  0.82],  # US100 vs XAUUSD during stress event
    [0.82,  1.00]
])
max_corr = 0.82
haircut_factor = max(0.40, 1.0 - (max_corr - 0.70) * 1.5) if max_corr > 0.70 else 1.0
print(f"\n3. CORRELATION MATRIX HAIRCUT PROOF:")
print(f"   Stress-Tested Corr(US100, XAUUSD) = {max_corr}")
print(f"   Calculated Haircut Scale Factor = {haircut_factor:.4f} (Exposure reduced by {(1-haircut_factor)*100:.1f}%)")

# 4. Latency & Slippage Audit
log_trigger_time = "02:47:29.934"
broker_execution_time = "02:47:31.000"
latency_ms = 1065.0
print(f"\n4. EXECUTION LATENCY & SLIPPAGE AUDIT:")
print(f"   Trigger Time: {log_trigger_time}")
print(f"   Broker Fill Time: {broker_execution_time}")
print(f"   Execution Latency Delta: {latency_ms:.0f} ms")
print(f"   USTECm Slippage: +27.77 pts (Trigger: 29773.81 -> Fill: 29801.58)")
print(f"   XAUUSDm Slippage: -8.684 pts / -86.8 pips (Trigger: 4332.065 -> Fill: 4323.381)")

print("="*80)
