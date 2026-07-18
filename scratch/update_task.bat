@echo off
echo =======================================================
echo          UPDATING NOWTRADING SCHEDULED TASK...
echo =======================================================
echo.

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "update_task.ps1"

if %ERRORLEVEL% EQU 0 (
    echo [OK] Task updated successfully.
) else (
    echo [ERROR] Failed to update task. Try running as Administrator.
)

pause
