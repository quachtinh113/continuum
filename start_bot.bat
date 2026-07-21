@echo off
title V9 Continuum - Institutional Quantitative Bot
color 0A

echo =======================================================
echo          V9 CONTINUUM - INITIALIZING BOT...
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

:: Stop old bot instance if running to ensure a clean start with the latest process
if exist logs\bot.pid set /p OLD_PID=<logs\bot.pid
if defined OLD_PID (
    echo [INFO] Stopping existing bot process PID: %OLD_PID%...
    taskkill /F /PID %OLD_PID% >nul 2>&1
    set OLD_PID=
)

:: Auto-restart loop (max 50 restarts to prevent infinite crash loops)
set /a RESTART_COUNT=0
set MAX_RESTARTS=50
set RESTART_DELAY=30

:start_loop
set /a RESTART_COUNT+=1

if %RESTART_COUNT% GTR %MAX_RESTARTS% (
    echo.
    echo =======================================================
    echo  ERROR: Max restarts reached [%MAX_RESTARTS%]. Bot will NOT restart.
    echo  Please check logs and fix the issue manually.
    echo =======================================================
    pause > nul
    exit /b 1
)

echo.
echo [%date% %time%] Starting bot (attempt %RESTART_COUNT%/%MAX_RESTARTS%)...
echo.

:: Run the bot
python -m v9_continuum.main

:: Check exit code
set EXIT_CODE=%ERRORLEVEL%

if %EXIT_CODE% EQU 0 (
    echo.
    echo =======================================================
    echo  Bot stopped gracefully [exit code 0]. Not restarting.
    echo =======================================================
    pause > nul
    exit /b 0
)

echo.
echo =======================================================
echo  Bot crashed with exit code %EXIT_CODE%.
echo  Restarting in %RESTART_DELAY% seconds...
echo  (Press Ctrl+C to cancel restart)
echo =======================================================

:: Wait before restart using ping (compatible with background/non-interactive tasks)
ping 127.0.0.1 -n %RESTART_DELAY% > nul

goto start_loop
