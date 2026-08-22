@echo off
cd /d "D:\05_Quant\v9 Continuum"
set PYTHONIOENCODING=utf-8
python scripts\daily_pnl_check.py >> logs\daily_check.log 2>&1
