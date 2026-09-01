' QiDong.vbs - Invest Tool silent launcher (double-click, no console window)
' Flow: kill old process on 8022 -> rebuild frontend if needed -> start backend hidden -> open browser
' See scripts\Start-App.ps1 for details.
Set objShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strRoot = fso.GetParentFolderName(WScript.ScriptFullName)
objShell.CurrentDirectory = strRoot
objShell.Run "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & strRoot & "\scripts\Start-App.ps1""", 0, False
