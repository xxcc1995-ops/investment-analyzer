@echo off
chcp 65001 >nul 2>&1

echo ========================================
echo   QuantDinger Stop
echo ========================================
echo.

set "QD_DIR=%USERPROFILE%\QuantDinger"
if not exist "%QD_DIR%" (
    echo [!] QuantDinger is not installed
    pause
    exit /b 1
)

cd /d "%QD_DIR%"
docker compose down

echo.
echo [+] QuantDinger stopped
echo.
pause
