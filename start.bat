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

:: Start backend (minimized)
start "Invest-Backend" /min cmd /c "cd /d "%ROOT%backend" && venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001"

:: Start frontend (minimized)
start "Invest-Frontend" /min cmd /c "cd /d "%ROOT%frontend" && npx vite --port 5173"

:: Wait for services
timeout /t 8 /nobreak >nul

:: Open browser
start "" http://localhost:5173

echo 已启动！前端: http://localhost:5173  后端: http://localhost:8001
echo 如需停止，请在任务管理器中结束 python 和 node 进程。
timeout /t 3 /nobreak >nul
