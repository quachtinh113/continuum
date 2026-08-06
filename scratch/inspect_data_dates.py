import pandas as pd
from pathlib import Path

def main():
    data_dir = Path("data/historical")
    for csv_file in sorted(data_dir.glob("*_M15.csv")):
        df = pd.read_csv(csv_file)
        df['time'] = pd.to_datetime(df['time'])
        print(f"File: {csv_file.name} | Shape: {df.shape} | Min Time: {df['time'].min()} | Max Time: {df['time'].max()}")

if __name__ == '__main__':
    main()
