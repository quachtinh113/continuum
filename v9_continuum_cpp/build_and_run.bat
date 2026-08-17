@echo off
setlocal
echo ================================================================
echo    CONTINUUM V9: C++ COMPILER AND TEST BUILD SCRIPT
echo ================================================================

where g++ >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo [1/2] Compiling Unit Test Runner with g++...
    g++ -std=c++14 -O3 -Iinclude tests/test_runner.cpp -o bin_tests.exe
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Test Compilation Failed!
        exit /b 1
    )
    echo [PASS] Compiled bin_tests.exe successfully!

    echo [2/2] Compiling Main Bot Engine with g++...
    g++ -std=c++14 -O3 -Iinclude src/main.cpp -o bin_bot.exe
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Bot Compilation Failed!
        exit /b 1
    )
    echo [PASS] Compiled bin_bot.exe successfully!

    echo.
    echo ================================================================
    echo    EXECUTING C++ UNIT TESTS AND BACKTEST PARITY VERIFICATION
    echo ================================================================
    bin_tests.exe
) else (
    echo [ERROR] g++ compiler not found in PATH!
    exit /b 1
)

endlocal
