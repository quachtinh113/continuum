import sys

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("==========================================================")
    print("      WORLDQUANT CAPITAL SCALING SIMULATION MATRIX")
    print("==========================================================")
    
    # Base strategy metrics on $1,000 account (Optimized 2-Asset Portfolio)
    base_equity = 1000.0
    monthly_pnl_base = 136.19  # +$31.43 / week * 4.33 weeks
    monthly_return_base = monthly_pnl_base / base_equity # 13.62%
    max_dd_pct_base = 0.2918    # 29.18% max historical drawdown on $1k
    target_monthly_pnl = 3000.0

    aums = [10000.0, 25000.0, 50000.0, 100000.0]

    print(f"Target Monthly PnL: ${target_monthly_pnl:,.2f}\n")
    print(f"{'AUM ($)':<10} │ {'Req. Monthly Return':<20} │ {'Lot Scale Factor':<18} │ {'Risk Per Trade (%)':<20} │ {'Max Drawdown (%)':<18} │ {'Status':<15}")
    print("-" * 110)

    for aum in aums:
        req_return = target_monthly_pnl / aum
        # Scale factor needed to achieve $3,000/mo
        pnl_multiplier = target_monthly_pnl / monthly_pnl_base
        # Lot scaling relative to base $1k
        lot_scale = pnl_multiplier * (1000.0 / aum)
        
        # Risk per trade
        risk_per_trade_pct = 0.30 * lot_scale
        
        # Projected Max Drawdown %
        proj_max_dd_pct = max_dd_pct_base * (req_return / monthly_return_base)
        
        status = "PASSED 🟢" if proj_max_dd_pct <= 0.10 else "REJECTED 🔴 (DD > 10%)"
        
        aum_str = f"${aum:,.0f}"
        print(f"{aum_str:<10} │ {req_return*100:>18.2f}% │ {lot_scale:>16.2f}x │ {risk_per_trade_pct:>18.2f}% │ {proj_max_dd_pct*100:>16.2f}% │ {status}")

    print("==========================================================")

if __name__ == '__main__':
    main()
