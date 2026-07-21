import os
import json

CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
_matrix_file = os.getenv("PORTFOLIO_MATRIX_FILE", "portfolio_matrix.json")
if os.path.isabs(_matrix_file):
    MATRIX_PATH = _matrix_file
else:
    _project_root = os.path.dirname(os.path.dirname(CONFIG_DIR))
    _root_path = os.path.join(_project_root, _matrix_file)
    if os.path.exists(_root_path):
        MATRIX_PATH = _root_path
    else:
        MATRIX_PATH = os.path.join(CONFIG_DIR, _matrix_file)

class PortfolioMatrixConfig:
    def __init__(self, path=None):
        self.path = path or MATRIX_PATH
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
        val = data.get("weekend_close_hour_utc", None)
        self.weekend_close_hour_utc = int(val) if val is not None else None

matrix_config = PortfolioMatrixConfig()
