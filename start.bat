@echo off
setlocal enabledelayedexpansion

set "ROOT=%~dp0"

:: 获取短路径名避免括号等特殊字符问题
for %%I in ("%ROOT%") do set "SHORT_ROOT=%%~sI"

echo ========================================
echo   新源的Invest工具 启动程序
echo ========================================
echo.
echo   [1] 本地启动 (Python + Node.js)
echo   [2] Docker启动 (docker-compose)
echo   [3] Docker构建并启动
echo   [4] Docker停止
echo   [5] Docker查看日志
echo.
set /p LAUNCH_MODE="请选择启动方式 (1-5, 默认1): "

if "%LAUNCH_MODE%"=="2" goto DOCKER_START
if "%LAUNCH_MODE%"=="3" goto DOCKER_BUILD
if "%LAUNCH_MODE%"=="4" goto DOCKER_STOP
if "%LAUNCH_MODE%"=="5" goto DOCKER_LOGS
goto LOCAL_START

:: ========================================
:: Docker启动
:: ========================================
:DOCKER_START
echo [INFO] 使用Docker启动服务...
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到Docker，请先安装Docker Desktop
    echo 下载地址: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)
cd /d "%ROOT%"
docker-compose up -d
if errorlevel 1 (
    echo [ERROR] Docker启动失败，请检查docker-compose.yml配置
    pause
    exit /b 1
)
echo.
echo ========================================
echo   Docker启动成功！
echo ========================================
echo.
echo   前端地址: http://localhost:5173
echo   后端地址: http://localhost:8002
echo.
echo   查看日志: docker-compose logs -f
echo   停止服务: start.bat 选择 [4]
echo ========================================
start "" http://localhost:5173
pause
exit /b 0

:DOCKER_BUILD
echo [INFO] 构建并启动Docker服务...
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到Docker，请先安装Docker Desktop
    pause
    exit /b 1
)
cd /d "%ROOT%"
echo [INFO] 构建镜像（首次可能需要几分钟）...
docker-compose build --no-cache
if errorlevel 1 (
    echo [ERROR] Docker构建失败
    pause
    exit /b 1
)
docker-compose up -d
if errorlevel 1 (
    echo [ERROR] Docker启动失败
    pause
    exit /b 1
)
echo.
echo ========================================
echo   Docker构建并启动成功！
echo ========================================
echo.
echo   前端地址: http://localhost:5173
echo   后端地址: http://localhost:8002
echo.
echo   查看日志: docker-compose logs -f
echo ========================================
start "" http://localhost:5173
pause
exit /b 0

:DOCKER_STOP
echo [INFO] 停止Docker服务...
cd /d "%ROOT%"
docker-compose down
echo [OK] Docker服务已停止
pause
exit /b 0

:DOCKER_LOGS
cd /d "%ROOT%"
docker-compose logs -f
pause
exit /b 0

:: ========================================
:: 本地启动
:: ========================================
:LOCAL_START
:: 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到Python，请先安装Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 检查Node.js环境
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到Node.js，请先安装Node.js 18+
    echo 下载地址: https://nodejs.org/
    pause
    exit /b 1
)

:: 检查venv是否存在
if not exist "%ROOT%backend\venv\Scripts\python.exe" (
    echo [INFO] 创建Python虚拟环境...
    cd /d "%ROOT%backend"
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo [INFO] 安装Python依赖...
    "%ROOT%backend\venv\Scripts\pip.exe" install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] 安装Python依赖失败
        pause
        exit /b 1
    )
)

:: 检查node_modules是否存在
if not exist "%ROOT%frontend\node_modules" (
    echo [INFO] 安装前端依赖...
    cd /d "%ROOT%frontend"
    call npm install
    if errorlevel 1 (
        echo [ERROR] 安装前端依赖失败
        pause
        exit /b 1
    )
)

:: 创建日志目录
if not exist "%ROOT%logs" mkdir "%ROOT%logs"

:: 检查端口是否被占用
netstat -ano 2>nul | findstr ":8002 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] 端口8002已被占用，尝试停止旧进程...
    for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8002 " ^| findstr "LISTENING"') do (
        taskkill /PID %%a /F >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
)

netstat -ano 2>nul | findstr ":5173 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] 端口5173已被占用，尝试停止旧进程...
    for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5173 " ^| findstr "LISTENING"') do (
        taskkill /PID %%a /F >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
)

echo.
echo [INFO] 启动后端服务...
:: 使用start命令启动后端，通过独立的bat文件避免路径问题
echo @echo off > "%ROOT%logs\start_backend.bat"
echo cd /d "%ROOT%backend" >> "%ROOT%logs\start_backend.bat"
echo "%ROOT%backend\venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8002 ^> "%ROOT%logs\backend.log" 2^>^&1 >> "%ROOT%logs\start_backend.bat"

start "Invest-Backend" /min cmd /c "%ROOT%logs\start_backend.bat"

echo [INFO] 启动前端服务...
start "Invest-Frontend" /min cmd /c "cd /d "%ROOT%frontend" && npx vite --port 5173 --host 0.0.0.0 > "%ROOT%logs\frontend.log" 2>&1"

:: 等待后端启动
echo [INFO] 等待服务启动...
set /a ATTEMPTS=0
:WAIT_BACKEND
set /a ATTEMPTS+=1
if %ATTEMPTS% GTR 30 (
    echo [ERROR] 后端启动超时，请检查日志: logs\backend.log
    echo [INFO] 查看日志命令: type logs\backend.log
    pause
    exit /b 1
)
powershell -Command "$c = New-Object System.Net.Sockets.TcpClient; try { $c.Connect('localhost', 8002); $c.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto WAIT_BACKEND
)
echo [OK] 后端已启动 (端口8002)

:: 等待前端启动
set /a ATTEMPTS=0
:WAIT_FRONTEND
set /a ATTEMPTS+=1
if %ATTEMPTS% GTR 30 (
    echo [ERROR] 前端启动超时，请检查日志: logs\frontend.log
    echo [INFO] 查看日志命令: type logs\frontend.log
    pause
    exit /b 1
)
powershell -Command "$c = New-Object System.Net.Sockets.TcpClient; try { $c.Connect('localhost', 5173); $c.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto WAIT_FRONTEND
)
echo [OK] 前端已启动 (端口5173)

echo.
echo ========================================
echo   启动成功！
echo ========================================
echo.
echo   前端地址: http://localhost:5173
echo   后端地址: http://localhost:8002
echo.
echo   日志文件:
echo     后端: logs\backend.log
echo     前端: logs\frontend.log
echo.
echo   停止服务: 运行 stop.bat
echo ========================================

:: 打开浏览器
start "" http://localhost:5173

:: 等待几秒后退出启动窗口
timeout /t 5 /nobreak >nul
