@echo off
setlocal

echo Stopping Invest Analyzer...

:: Kill by window title (matches start.bat's start "Invest-Backend" / "Invest-Frontend")
taskkill /FI "WINDOWTITLE eq Invest-Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Invest-Frontend*" /F >nul 2>&1

:: Kill by port (more reliable fallback)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8002 " ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173 " ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)

echo Done. Backend (8002) and Frontend (5173) stopped.
ping -n 3 127.0.0.1 >nul
