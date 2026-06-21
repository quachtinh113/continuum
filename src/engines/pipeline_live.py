import os
import json
import pandas as pd
from src.xgboost_gatekeeper import MLGatekeeper

def run_shadow_audit():
    """
    Tích hợp ML Gatekeeper vào pipeline thực thi để thực hiện 'Shadow Audit'.
    Trong thực tế, pipeline này sẽ chạy real-time trong tick loop. 
    Để mô phỏng 'Shadow Audit', chúng ta sẽ duyệt qua dữ liệu đã có.
    """
    print("Starting ML Shadow Audit in OBSERVE_ONLY mode...")
    
    # Initialize Gatekeeper
    gatekeeper = MLGatekeeper("src/ml/gatekeeper_v1.model")
    if not gatekeeper.is_ready:
        print("ML Gatekeeper is not ready. Aborting.")
        return

    # Load data to simulate the signal tick loop
    df = pd.read_csv('logs/training_data.csv')
    df['entry_time'] = pd.to_datetime(df['entry_time'])
    
    os.makedirs('logs', exist_ok=True)
    os.makedirs('reports', exist_ok=True)
    
    log_file = 'logs/ml_veto_simulation.jsonl'
    
    threat_is_loss = 0
    threat_is_profit = 0
    total_threats = 0
    
    with open(log_file, 'w') as f:
        for idx, row in df.iterrows():
            symbol = row['symbol']
            time = row['entry_time']
            
            # Reconstruct Price for the Volatility Index
            price = 1.0 # Default fallback
            hist_file = f'data/historical/{symbol}_M15.csv'
            if os.path.exists(hist_file):
                hist_df = pd.read_csv(hist_file)
                hist_df['time'] = pd.to_datetime(hist_df['time'], utc=True)
                closest_row = hist_df.iloc[(hist_df['time'] - time).abs().argsort()[:1]]
                if not closest_row.empty:
                    price = closest_row['close'].values[0]
            
            features = {
                'RSI_M15': row['RSI_M15'],
                'RSI_H1': row['RSI_H1'],
                'RSI_H4': row['RSI_H4'],
                'ADX': row['ADX'],
                'ATR': row['ATR'],
                'hour': row['hour']
            }
            
            # In tick loop, after signal from Signal_Engine, run score_trade
            score = gatekeeper.score_trade(features, price, int(row['hour']))
            
            if score is None:
                continue
                
            is_threat = score > 0.8
            actual_pnl = row['profit_usd']
            
            log_record = {
                "timestamp": time.isoformat(),
                "symbol": symbol,
                "signal": row['direction'],
                "score": score,
                "actual_pnl_after_exit": actual_pnl,
                "ml_predicted_loss_threat": is_threat
            }
            f.write(json.dumps(log_record) + "\n")
            
            if is_threat:
                total_threats += 1
                if actual_pnl <= 0:
                    threat_is_loss += 1
                else:
                    threat_is_profit += 1
                    
    print(f"Shadow audit completed. Wrote {len(df)} records to {log_file}")
    
    # 4. Reporting
    report_path = 'reports/ml_shadow_audit_summary.md'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# ML Shadow Audit Summary\n\n")
        f.write("Báo cáo đối soát (Shadow Audit) cho mô hình XGBoost Gatekeeper trong trạng thái OBSERVE_ONLY.\n\n")
        f.write(f"- **Tổng số lệnh ML dự báo THREAT (Score > 0.8)**: {total_threats}\n")
        f.write(f"- **Số lệnh ML dự báo THREAT mà thực tế là LOSS (True Positives)**: {threat_is_loss}\n")
        f.write(f"- **Số lệnh ML dự báo THREAT mà thực tế là PROFIT (False Positives)**: {threat_is_profit}\n")
        
    print(f"Report generated at {report_path}")

if __name__ == "__main__":
    run_shadow_audit()
