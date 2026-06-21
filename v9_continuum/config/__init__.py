import os
import json

CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
MATRIX_PATH = os.path.join(CONFIG_DIR, "portfolio_matrix.json")

class PortfolioMatrixConfig:
    def __init__(self, path=MATRIX_PATH):
        self.path = path
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        
        self.max_open_positions = int(data.get("max_open_positions", 3))
        self.max_total_risk_percent = float(data.get("max_total_risk_percent", 2.0))
        self.max_daily_drawdown_percent = float(data.get("max_daily_drawdown_percent", 3.0))
        self.max_usd_exposure = int(data.get("max_usd_exposure", 2))
        self.max_gold_index_combo = int(data.get("max_gold_index_combo", 1))
        self.news_lock_minutes = int(data.get("news_lock_minutes", 30))
        self.holding_reduce_hours = float(data.get("holding_reduce_hours", 12.0))
        self.max_holding_hours = float(data.get("max_holding_hours", 18.0))

matrix_config = PortfolioMatrixConfig()
