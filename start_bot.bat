@echo off
title V9 Continuum - Institutional Quantitative Bot
color 0A

echo =======================================================
echo          V9 CONTINUUM - INITIALIZING BOT...
echo =======================================================
echo.

:: Ensure we are in the correct directory
cd /d "%~dp0"

:: Set utf-8 encoding for proper emoji display
set PYTHONIOENCODING=utf-8

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
