@echo off
TITLE V9 Continuum - Weekly Rolling ML Retrain Pipeline
echo =======================================================
echo     V9 CONTINUUM - WEEKLY ROLLING ML RETRAIN
echo =======================================================
echo.
cd /d "%~dp0\.."

python scripts\weekly_rolling_retrain.py

echo.
echo =======================================================
echo     RETRAIN PIPELINE EXECUTION COMPLETED
echo =======================================================
pause
