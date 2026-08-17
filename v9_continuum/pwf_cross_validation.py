import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Generator, Tuple, List

class PurgedWalkForwardCV:
    """
    Marcos López de Prado's Purged Walk-Forward Cross Validation with Embargo.
    Default Config:
    - 36 Months Total (2023-08-01 to 2026-08-01)
    - Train Window: 12 Months
    - Test Window: 3 Months
    - Embargo: 14 Days
    - Purging: Purges samples whose labels overlap with test window boundaries.
    """
    def __init__(
        self,
        start_date: str = "2023-08-01",
        end_date: str = "2026-08-01",
        train_months: int = 12,
        test_months: int = 3,
        embargo_days: int = 14
    ):
        self.start_date = pd.to_datetime(start_date, utc=True)
        self.end_date = pd.to_datetime(end_date, utc=True)
        self.train_months = train_months
        self.test_months = test_months
        self.embargo_days = embargo_days

    def split(self, df: pd.DataFrame) -> Generator[Tuple[List[int], List[int], datetime, datetime, datetime, datetime], None, None]:
        """
        Yields (train_indices, test_indices, t_train_start, t_train_end, t_test_start, t_test_end)
        with strict purging and embargo applied.
        """
        if "timestamp" in df.columns:
            df_time = pd.to_datetime(df["timestamp"], utc=True)
        else:
            df_time = pd.to_datetime(df.index, utc=True)

        current_train_start = self.start_date

        while True:
            current_train_end = current_train_start + pd.DateOffset(months=self.train_months)
            current_test_start = current_train_end
            current_test_end = current_test_start + pd.DateOffset(months=self.test_months)

            if current_test_end > self.end_date:
                break

            # 1. Test Mask
            test_mask = (df_time >= current_test_start) & (df_time < current_test_end)
            test_indices = df.index[test_mask].tolist()

            if not test_indices:
                current_train_start = current_train_start + pd.DateOffset(months=self.test_months)
                continue

            # 2. Raw Train Mask
            train_mask = (df_time >= current_train_start) & (df_time < current_train_end)

            # 3. Purging & Embargo Application
            # Drop the last 14 days of train window to prevent autocorrelation leakage into test
            embargo_boundary = current_train_end - pd.Timedelta(days=self.embargo_days)
            purged_train_mask = train_mask & (df_time < embargo_boundary)

            train_indices = df.index[purged_train_mask].tolist()

            # Ensure python datetime objects
            t_tr_s = current_train_start.to_pydatetime()
            t_tr_e = current_train_end.to_pydatetime()
            t_te_s = current_test_start.to_pydatetime()
            t_te_e = current_test_end.to_pydatetime()

            yield train_indices, test_indices, t_tr_s, t_tr_e, t_te_s, t_te_e

            # Slide window by test_months (e.g. 3 months)
            current_train_start = current_train_start + pd.DateOffset(months=self.test_months)
