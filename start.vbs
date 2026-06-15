Set objShell = CreateObject("WScript.Shell")
strRoot = objShell.CurrentDirectory & "\"

' 检查后端环境
If Not objShell.FileSystemObject.FileExists(strRoot & "backend\venv\Scripts\python.exe") Then
    MsgBox "Python虚拟环境不存在！" & vbCrLf & vbCrLf & _
        "请先运行:" & vbCrLf & _
        "cd backend" & vbCrLf & _
        "python -m venv venv" & vbCrLf & _
        "venv\Scripts\pip install -r requirements.txt", 16, "Invest Tool - 错误"
    WScript.Quit 1
End If

' 检查前端依赖
If Not objShell.FileSystemObject.FolderExists(strRoot & "frontend\node_modules") Then
    MsgBox "前端依赖未安装，正在执行 npm install..." & vbCrLf & "请稍候...", 64, "Invest Tool"
    objShell.Run "cmd /c cd /d """ & strRoot & "frontend"" && npm install", 1, True
End If

' 启动后端
objShell.Run "cmd /c cd /d """ & strRoot & "backend"" && venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8002", 0, False

' 启动前端
objShell.Run "cmd /c cd /d """ & strRoot & "frontend"" && npx vite --port 5173", 0, False

' 等待服务就绪（最多30秒）
Dim bReady, fReady
bReady = False
fReady = False

For i = 1 To 30
    WScript.Sleep 1000
    ' 检查后端端口
    If Not bReady Then
        Set oExec = objShell.Exec("cmd /c powershell -Command ""$c = New-Object System.Net.Sockets.TcpClient; try { $c.Connect('localhost', 8002); $c.Close(); exit 0 } catch { exit 1 }""")
        oExec.StdOut.ReadAll
        If oExec.ExitCode = 0 Then bReady = True
    End If
    ' 检查前端端口
    If Not fReady Then
        Set oExec2 = objShell.Exec("cmd /c powershell -Command ""$c = New-Object System.Net.Sockets.TcpClient; try { $c.Connect('localhost', 5173); $c.Close(); exit 0 } catch { exit 1 }""")
        oExec2.StdOut.ReadAll
        If oExec2.ExitCode = 0 Then fReady = True
    End If
    If bReady And fReady Then Exit For
Next

If bReady And fReady Then
    objShell.Run "http://localhost:5173", 1, False
    MsgBox "启动成功！" & vbCrLf & vbCrLf & _
        "前端: http://localhost:5173" & vbCrLf & _
        "后端: http://localhost:8002" & vbCrLf & vbCrLf & _
        "停止: 运行 stop.bat 或在任务管理器结束 python/node 进程", 64, "Invest Tool"
Else
    Dim errMsg
    errMsg = "启动超时！" & vbCrLf & vbCrLf
    If Not bReady Then errMsg = errMsg & "后端(8002)未就绪 - 请检查 backend/venv 和日志" & vbCrLf
    If Not fReady Then errMsg = errMsg & "前端(5173)未就绪 - 请检查 node_modules 和日志" & vbCrLf
    errMsg = errMsg & vbCrLf & "建议运行 start.bat 查看详细错误信息"
    MsgBox errMsg, 16, "Invest Tool - 错误"
End If
