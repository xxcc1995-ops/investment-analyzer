@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo ========================================
echo   QuantDinger Launcher
echo ========================================
echo.

:: Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Docker is not running. Starting Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo [*] Waiting for Docker (up to 120s)...
    :wait_docker
    timeout /t 5 /nobreak >nul
    docker info >nul 2>&1
    if !errorlevel! neq 0 (
        echo [*] Still waiting...
        goto wait_docker
    )
    echo [+] Docker is ready!
) else (
    echo [+] Docker is running
)

:: Check if project exists
set "QD_DIR=%USERPROFILE%\QuantDinger"
if not exist "%QD_DIR%\docker-compose.yml" (
    echo.
    echo [*] First run - cloning QuantDinger...
    git clone --depth 1 https://github.com/brokermr810/QuantDinger.git "%QD_DIR%"
    if !errorlevel! neq 0 (
        echo [!] Clone failed. Check network or proxy settings.
        pause
        exit /b 1
    )
    echo [+] Clone done
)

:: Create root .env with mirror and port overrides
echo [*] Configuring...
(
    echo IMAGE_PREFIX=docker.m.daocloud.io/library/
    echo DB_PORT=127.0.0.1:5433
    echo REDIS_PORT=127.0.0.1:6380
) > "%QD_DIR%\.env"

:: Create backend .env if not exists
if not exist "%QD_DIR%\backend_api_python\.env" (
    copy "%QD_DIR%\backend_api_python\env.example" "%QD_DIR%\backend_api_python\.env" >nul
    :: Generate SECRET_KEY
    for /f "tokens=*" %%i in ('python -c "import secrets; print(secrets.token_hex(32))"') do set "SECRET=%%i"
    powershell -Command "(Get-Content '%QD_DIR%\backend_api_python\.env') -replace '^SECRET_KEY=.*', 'SECRET_KEY=!SECRET!' | Set-Content '%QD_DIR%\backend_api_python\.env' -Encoding utf8"
    echo [+] SECRET_KEY generated
)

:: Start services
echo.
echo [*] Starting QuantDinger...
cd /d "%QD_DIR%"
docker compose up -d

echo.
echo ========================================
echo   [+] QuantDinger started!
echo   [*] URL:  http://localhost:8888
echo   [*] User: quantdinger / 123456
echo   [*] Please change the default password
echo ========================================
echo.
timeout /t 3 >nul
start "" "http://localhost:8888"
