' TingZhi.vbs - Invest Tool silent stopper (kills the backend on port 8022)
Set objShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strRoot = fso.GetParentFolderName(WScript.ScriptFullName)
objShell.Run "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & strRoot & "\scripts\Stop-App.ps1""", 0, False
