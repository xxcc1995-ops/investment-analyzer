@echo off
setlocal

set "ROOT=%~dp0"

:: Check venv exists
if not exist "%ROOT%backend\venv\Scripts\python.exe" (
    echo [ERROR] Python venv not found at backend\venv
    echo Please run: cd backend && python -m venv venv && venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

:: Check node_modules exists
if not exist "%ROOT%frontend\node_modules" (
    echo Installing dependencies...
    cd /d "%ROOT%frontend" && npm install
)

:: Check for port conflicts
netstat -ano | findstr ":8002 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [ERROR] Port 8002 is already in use. Run stop.bat first or kill the process.
    pause
    exit /b 1
)
netstat -ano | findstr ":5173 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [ERROR] Port 5173 is already in use. Run stop.bat first or kill the process.
    pause
    exit /b 1
)

:: Start backend (minimized)
start "Invest-Backend" /min cmd /c "cd /d ""%ROOT%backend"" && venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8002"

:: Start frontend (minimized)
start "Invest-Frontend" /min cmd /c "cd /d ""%ROOT%frontend"" && npx vite --port 5173"

:: Poll for backend readiness (max 30s)
echo Waiting for services...
set /a ATTEMPTS=0
:WAIT_BACKEND
set /a ATTEMPTS+=1
if %ATTEMPTS% GTR 30 (
    echo [ERROR] Backend failed to start within 30 seconds.
    pause
    exit /b 1
)
powershell -Command "$c = New-Object System.Net.Sockets.TcpClient; try { $c.Connect('localhost', 8002); $c.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    ping -n 2 127.0.0.1 >nul
    goto WAIT_BACKEND
)
echo Backend ready on port 8002.

:: Poll for frontend readiness (max 30s)
set /a ATTEMPTS=0
:WAIT_FRONTEND
set /a ATTEMPTS+=1
if %ATTEMPTS% GTR 30 (
    echo [ERROR] Frontend failed to start within 30 seconds.
    pause
    exit /b 1
)
powershell -Command "$c = New-Object System.Net.Sockets.TcpClient; try { $c.Connect('localhost', 5173); $c.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    ping -n 2 127.0.0.1 >nul
    goto WAIT_FRONTEND
)
echo Frontend ready on port 5173.

:: Open browser
start "" http://localhost:5173

echo.
echo Started! Frontend: http://localhost:5173  Backend: http://localhost:8002
echo Run stop.bat to stop all services.
ping -n 4 127.0.0.1 >nul
