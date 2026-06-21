@echo off
REM NowTrading V9 — Daily ML Retrain Scheduler
REM Runs daily_retrain.py every day at 05:00 AM Vietnam time (22:00 UTC)
REM Register this task with Windows Task Scheduler via: schedule_retrain.bat INSTALL

SET PROJECT_DIR=d:\05_Quant\NOWTRAEDING
SET PYTHON=python
SET SCRIPT=%PROJECT_DIR%\scripts\daily_retrain.py
SET LOG=%PROJECT_DIR%\logs\retrain_scheduler.log
SET TASK_NAME=NowTrading_DailyRetrain

IF "%1"=="INSTALL" GOTO INSTALL
IF "%1"=="UNINSTALL" GOTO UNINSTALL
IF "%1"=="RUN" GOTO RUN

:DEFAULT
echo Usage:
echo   schedule_retrain.bat INSTALL    - Register Windows Task Scheduler (22:00 UTC daily)
echo   schedule_retrain.bat UNINSTALL  - Remove from Task Scheduler
echo   schedule_retrain.bat RUN        - Run retrain manually now
GOTO END

:INSTALL
echo Installing scheduled task: %TASK_NAME%
echo Task will run at 05:00 AM local time (please verify UTC offset)
schtasks /Create /TN "%TASK_NAME%" /TR "cmd /c %PYTHON% \"%SCRIPT%\" >> \"%LOG%\" 2>&1" /SC DAILY /ST 05:00 /F /RL HIGHEST
IF %ERRORLEVEL%==0 (
    echo [OK] Task registered successfully.
    schtasks /Query /TN "%TASK_NAME%"
) ELSE (
    echo [ERROR] Failed to register task. Try running as Administrator.
)
GOTO END

:UNINSTALL
echo Removing scheduled task: %TASK_NAME%
schtasks /Delete /TN "%TASK_NAME%" /F
IF %ERRORLEVEL%==0 (
    echo [OK] Task removed.
) ELSE (
    echo [ERROR] Task not found or removal failed.
)
GOTO END

:RUN
echo Running daily retrain manually...
%PYTHON% "%SCRIPT%"
GOTO END

:END
