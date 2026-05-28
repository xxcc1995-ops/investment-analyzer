Set objShell = CreateObject("WScript.Shell")
strRoot = objShell.CurrentDirectory & "\"

objShell.Run "cmd /c cd /d """ & strRoot & "backend"" && venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001", 0, False

objShell.Run "cmd /c cd /d """ & strRoot & "frontend"" && npx vite --port 5173", 0, False

WScript.Sleep 15000

objShell.Run "http://localhost:5173", 1, False

MsgBox "Started!" & vbCrLf & vbCrLf & _
    "Frontend: http://localhost:5173" & vbCrLf & _
    "Backend: http://localhost:8001" & vbCrLf & vbCrLf & _
    "To stop: end python/node processes in Task Manager.", 64, "Invest Tool"