@echo off
title V9 Continuum - Watchdog Monitor
color 0C

echo =======================================================
echo          V9 CONTINUUM - WATCHDOG MONITOR...
echo =======================================================
echo.

cd /d "%~dp0"
if not exist "v9_continuum" (
    cd /d "d:\05_Quant\v9 Continuum"
)

:: Kích hoạt môi trường ảo nếu tồn tại
if exist .\venv\Scripts\activate.bat (
    call .\venv\Scripts\activate.bat
) else if exist .\.venv\Scripts\activate.bat (
    call .\.venv\Scripts\activate.bat
) else (
    echo [WARNING] Khong tim thay thu muc .\venv hoac .\.venv. Se dung Python he thong.
)

:: Set utf-8 encoding for proper emoji display
set PYTHONIOENCODING=utf-8

:: Chạy watchdog python script
python scratch/watchdog.py

pause
