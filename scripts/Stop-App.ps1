# Stop-App.ps1 - 静默停止「新源Invest工具」（结束占用 8022 的后端进程）
$ErrorActionPreference = "Continue"
$PORT = 8022

$conns = Get-NetTCPConnection -LocalPort $PORT -State Listen -ErrorAction SilentlyContinue
if ($conns) {
    $procIds = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($p in $procIds) {
        if ($p -gt 0 -and $p -ne $PID) {
            try { Stop-Process -Id $p -Force -ErrorAction Stop } catch {}
        }
    }
}

try {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $ni = New-Object System.Windows.Forms.NotifyIcon
    $ni.Icon = [System.Drawing.SystemIcons]::Information
    $ni.Visible = $true
    $ni.BalloonTipTitle = "投资分析器"
    $ni.BalloonTipText  = "已停止"
    $ni.ShowBalloonTip(3000)
    Start-Sleep -Seconds 2
    $ni.Dispose()
} catch {}
