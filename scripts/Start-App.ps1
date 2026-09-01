# Start-App.ps1 - 静默启动「新源Invest工具」（正式模式：单进程 8022，无命令行窗口）
# 由 启动.vbs 以隐藏方式调用。流程：
#   1. 强杀占用 8022 的旧进程（含挂死进程；杀不掉则自提权重试一次）
#   2. 前端 dist 缺失或源码比 dist 新 → 自动 vite build（约1-3分钟）
#   3. 隐藏启动后端 uvicorn（日志写入 logs\backend.log）
#   4. 等待 /health 就绪（最长180秒，lifespan 初始化较慢）
#   5. 托盘气泡通知 + 自动打开浏览器
param([switch]$Elevated)

$ErrorActionPreference = "Continue"
$ROOT    = Split-Path -Parent $PSScriptRoot
$beDir   = Join-Path $ROOT "backend"
$feDir   = Join-Path $ROOT "frontend"
$distIdx = Join-Path $feDir "dist\index.html"
$logDir  = Join-Path $ROOT "logs"
$beLog   = Join-Path $logDir "backend.log"
$beErrLog = Join-Path $logDir "backend-error.log"
$buildLog = Join-Path $logDir "frontend-build.log"
$PORT    = 8022

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$appLog = Join-Path $logDir "start-app.log"

function Write-Log($msg) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg" | Out-File $appLog -Append -Encoding utf8
}
Write-Log "=== Start-App 开始 (Elevated=$Elevated) ==="

$script:icons = @()
function Show-Toast($title, $msg, $sec = 6) {
    try {
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -AssemblyName System.Drawing
        $ni = New-Object System.Windows.Forms.NotifyIcon
        $ni.Icon = [System.Drawing.SystemIcons]::Information
        $ni.Visible = $true
        $ni.BalloonTipTitle = $title
        $ni.BalloonTipText  = $msg
        $ni.ShowBalloonTip($sec * 1000)
        $script:icons += $ni
    } catch {}
}

function Test-PortFree($port) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $c.Connect('127.0.0.1', $port)
        $c.Close()
        return $false
    } catch {
        return $true
    }
}

function Kill-Port($port) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { return }
    $procIds = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($p in $procIds) {
        if ($p -gt 0 -and $p -ne $PID) {
            try {
                Stop-Process -Id $p -Force -ErrorAction Stop
                "$(Get-Date -Format 'HH:mm:ss') killed PID $p on port $port" | Out-File $beErrLog -Append -Encoding utf8
            } catch {}
        }
    }
    Start-Sleep -Seconds 1
}

# ---------- 1. 释放 8022（挂死/旧代码一律强杀重启） ----------
if (-not (Test-PortFree $PORT)) {
    Write-Log "端口 $PORT 被占用，执行强杀"
    Kill-Port $PORT
    # 进程异步退出，最多等 10 秒让端口真正释放
    for ($i = 0; $i -lt 10; $i++) {
        if (Test-PortFree $PORT) { break }
        Start-Sleep -Seconds 1
    }
}
if (-not (Test-PortFree $PORT)) {
    if (-not $Elevated) {
        # 普通权限杀不掉（旧进程可能是管理员启动的）→ 自提权重跑一次
        Write-Log "端口仍被占用，自提权重试"
        Start-Process powershell -Verb RunAs -WindowStyle Hidden -ArgumentList "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSCommandPath`" -Elevated"
        exit 0
    } else {
        Write-Log "端口 $PORT 无法释放，放弃"
        Show-Toast "投资分析器" "端口 $PORT 被占用且无法释放，请手动检查后重试" 10
        exit 1
    }
}
Write-Log "端口 $PORT 已就绪"

Show-Toast "投资分析器" "正在启动，请稍候…" 4

# ---------- 2. 前端构建（dist 缺失或源码更新时） ----------
$needBuild = -not (Test-Path $distIdx)
if (-not $needBuild) {
    $distTime = (Get-Item $distIdx).LastWriteTime
    $srcNewest = Get-ChildItem (Join-Path $feDir "src") -Recurse -File -ErrorAction SilentlyContinue |
                 Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($srcNewest -and $srcNewest.LastWriteTime -gt $distTime) { $needBuild = $true }
}
if ($needBuild) {
    $node = (Get-Command node -ErrorAction SilentlyContinue).Source
    if ($node) {
        Write-Log "开始前端构建"
        Show-Toast "投资分析器" "检测到前端更新，正在构建（约1-3分钟）…" 8
        Start-Process cmd.exe -ArgumentList "/c","cd /d `"$feDir`" && npx vite build > `"$buildLog`" 2>&1" -Wait -WindowStyle Hidden
        Write-Log "前端构建结束"
    } else {
        Write-Log "未找到 node，跳过构建"
        Show-Toast "投资分析器" "未找到 node，无法构建前端；将使用现有 dist" 8
    }
}

# ---------- 3. 启动后端（隐藏窗口） ----------
$py = Join-Path $beDir "venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Show-Toast "投资分析器" "未找到后端虚拟环境 $py" 10
    exit
}
Start-Process -FilePath $py `
    -ArgumentList "-m","uvicorn","app.main:app","--port","$PORT","--no-use-colors" `
    -WorkingDirectory $beDir -WindowStyle Hidden `
    -RedirectStandardOutput $beLog -RedirectStandardError $beErrLog
Write-Log "后端进程已启动，等待健康检查"

# ---------- 4. 等待就绪 ----------
$ok = $false
for ($i = 0; $i -lt 180; $i++) {
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:$PORT/health" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch {}
    Start-Sleep -Seconds 1
}

# ---------- 5. 完成 ----------
if ($ok) {
    Write-Log "健康检查通过，打开浏览器"
    Show-Toast "投资分析器已就绪" "正在打开 http://127.0.0.1:$PORT" 5
    Start-Process "http://127.0.0.1:$PORT"
} else {
    Write-Log "健康检查超时（180秒）"
    Show-Toast "投资分析器启动失败" "请查看 logs\backend-error.log" 12
}
Start-Sleep -Seconds 2
foreach ($ni in $script:icons) { $ni.Dispose() }
exit 0
