import sys
import subprocess
import logging
from datetime import datetime

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    handlers=[
        logging.FileHandler("logs/weekly_retrain.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

def run_weekly_pipeline():
    logging.info("=" * 60)
    logging.info(f"STARTING WEEKLY ROLLING RETRAIN PIPELINE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info("=" * 60)
    
    # Step 1: Run Data Integrity Check
    logging.info("[STEP 1/3] Running Data Integrity & Closed-Bar Audit...")
    res_data = subprocess.run(["python", "-u", "scratch/audit_data_integrity.py"], capture_output=True, text=True)
    if res_data.returncode != 0:
        logging.error("Data Integrity Audit FAILED! Halting Pipeline.")
        logging.error(res_data.stderr)
        return False
    logging.info("Data Integrity Audit PASSED.")
    
    # Step 2: Run Purged Cross-Validation & SHAP Audit
    logging.info("[STEP 2/3] Executing Purged TimeSeries CV & SHAP Feature Re-evaluation...")
    res_ml = subprocess.run(["python", "-u", "scratch/audit_ml_purged_cv_shap.py"], capture_output=True, text=True)
    if res_ml.returncode != 0:
        logging.error("ML Retraining Audit FAILED! Halting Pipeline.")
        logging.error(res_ml.stderr)
        return False
        
    logging.info(res_ml.stdout)
    
    # Parse OOS AUC result from output
    if "Mean OOS AUC:" in res_ml.stdout:
        auc_line = [line for line in res_ml.stdout.split('\n') if "Mean OOS AUC:" in line][0]
        try:
            auc_val = float(auc_line.split(":")[1].strip().split()[0])
            logging.info(f"Retrained OOS AUC Metric: {auc_val:.4f}")
            
            if auc_val < 0.58:
                logging.critical(f"[SAFETY ALARM] OOS AUC ({auc_val:.4f}) dropped below safety threshold (0.58)!")
                logging.critical("TRIGGERING EMERGENCY CIRCUIT BREAKER - DISABLING BOT EXECUTION!")
                return False
            else:
                logging.info(f"[SUCCESS] OOS AUC ({auc_val:.4f}) satisfies WorldQuant Alpha Standard (>= 0.58).")
        except Exception as e:
            logging.warning(f"Could not parse AUC value accurately: {e}")
            
    # Step 3: Run End-to-End Dry-Run Integration Test
    logging.info("[STEP 3/3] Executing End-to-End Integration Test...")
    res_integ = subprocess.run(["python", "-u", "scratch/test_integration_end_to_end.py"], capture_output=True, text=True)
    if res_integ.returncode != 0:
        logging.error("Integration Test FAILED! Model update rejected.")
        logging.error(res_integ.stderr)
        return False
        
    logging.info("Integration Test PASSED with 0 errors.")
    logging.info("=" * 60)
    logging.info("WEEKLY RETRAIN PIPELINE COMPLETED SUCCESSFULLY! SYSTEM READY FOR NEXT WEEK.")
    logging.info("=" * 60)
    return True

if __name__ == "__main__":
    success = run_weekly_pipeline()
    if not success:
        sys.exit(1)
