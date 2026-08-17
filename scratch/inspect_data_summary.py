import glob
import pandas as pd
from pathlib import Path

def inspect_data():
    files = sorted(glob.glob("data/historical/*_H1.csv"))
    for f in files:
        df = pd.read_csv(f)
        print(f"{Path(f).name:20s}: {df['time'].iloc[0]} -> {df['time'].iloc[-1]} ({len(df)} bars)")

if __name__ == "__main__":
    inspect_data()
