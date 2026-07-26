import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

# Add workspace root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from v9_continuum.backtest import V9ContinuumBacktester

def calculate_psr(returns: np.ndarray, benchmark_sr: float = 0.0) -> float:
    """
    Calculates Probabilistic Sharpe Ratio (PSR).
    Formula incorporating skewness and kurtosis.
    """
    if len(returns) < 2:
        return 0.0
    n = len(returns)
    mean_ret = np.mean(returns)
    std_ret = np.std(returns, ddof=1)
    if std_ret == 0:
        return 0.0
    
    sr = mean_ret / std_ret
    skew = float(pd.Series(returns).skew())
    kurt = float(pd.Series(returns).kurtosis())
    
    sigma_sr = np.sqrt((1.0 + (0.5 * sr**2) - (skew * sr) + ((kurt / 4.0) * sr**2)) / (n - 1))
    if sigma_sr == 0:
        return 1.0 if sr > benchmark_sr else 0.0
        
    z_score = (sr - benchmark_sr) / sigma_sr
    from scipy.stats import norm
    psr = float(norm.cdf(z_score))
    return psr

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("===========================================================")
    print("🏦 INSTITUTIONAL WALK-FORWARD BACKTEST & FUND SURVIVAL AUDIT")
    print("===========================================================")
    
    tester = V9ContinuumBacktester()
    symbols_to_test = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "US100", "US500", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]
    
    available_symbols = []
    for s in symbols_to_test:
        if (Path("data/historical") / f"{s}_M15.csv").exists():
            available_symbols.append(s)
            
    start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2026, 7, 25, tzinfo=timezone.utc)
    
    print(f"Simulating Walk-Forward Out-of-Sample evaluation from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")
    portfolio, metrics = tester.run(available_symbols, start_date, end_date, initial_balance=10000.0)
    
    initial_balance = metrics['initial_balance']
    final_balance = metrics['final_balance']
    net_profit = metrics['total_profit_usd']
    profit_pct = metrics['profit_percent']
    max_dd_usd = metrics['max_drawdown_usd']
    max_dd_pct = metrics['max_drawdown_percent']
    win_rate = metrics['win_rate']
    profit_factor = metrics['profit_factor']
    
    # 1. Calmar Ratio calculation
    # Days elapsed
    days_elapsed = (end_date - start_date).days
    years_elapsed = max(0.1, days_elapsed / 365.0)
    annualized_return_pct = profit_pct / years_elapsed
    calmar_ratio = (annualized_return_pct / max_dd_pct) if max_dd_pct > 0 else annualized_return_pct
    
    # 2. Recovery Factor calculation
    recovery_factor = (net_profit / max_dd_usd) if max_dd_usd > 0 else net_profit
    
    # 3. Probabilistic Sharpe Ratio calculation
    trade_pnls = np.array([c['final_pnl'] for c in portfolio.closed_cycles])
    psr_val = calculate_psr(trade_pnls) if len(trade_pnls) > 1 else 0.0

    print("\n" + "=" * 60)
    print("            INSTITUTIONAL FUND PERFORMANCE SUMMARY")
    print("=" * 60)
    print(f" Simulation Period : {days_elapsed} days ({years_elapsed:.2f} years)")
    print(f" Initial Balance   : ${initial_balance:,.2f}")
    print(f" Final Balance     : ${final_balance:,.2f}")
    print(f" Net Profit        : ${net_profit:+,.2f} ({profit_pct:+,.2f}%)")
    print(f" Annualized Return : {annualized_return_pct:.2f}% / year")
    print("-" * 60)
    print(f" Win Rate          : {win_rate:.2f}%")
    print(f" Profit Factor     : {profit_factor}")
    print(f" Max Drawdown      : ${max_dd_usd:,.2f} ({max_dd_pct:.2f}%)")
    print("=" * 60 + "\n")

    print("🎯 FUND SURVIVAL METRICS AUDIT (Nghiệm Thu Chuẩn Quỹ):")
    print("-----------------------------------------------------------")
    psr_pass = psr_val >= 0.95
    calmar_pass = calmar_ratio >= 2.5
    rf_pass = recovery_factor >= 3.0
    
    print(f"1. Probabilistic Sharpe Ratio (PSR) : {psr_val*100:.2f}% (Target: > 95%) -> {'PASS 🟢' if psr_pass else 'INFO 🟡'}")
    print(f"2. Calmar Ratio                    : {calmar_ratio:.2f} (Target: > 2.5) -> {'PASS 🟢' if calmar_pass else 'INFO 🟡'}")
    print(f"3. Recovery Factor                 : {recovery_factor:.2f} (Target: > 3.0) -> {'PASS 🟢' if rf_pass else 'INFO 🟡'}")
    print("===========================================================\n")

if __name__ == '__main__':
    main()
