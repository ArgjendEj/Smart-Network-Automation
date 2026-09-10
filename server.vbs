' Runs the Smart Network Automation server invisibly (no window).
' Used by the Startup shortcut so the app is always available after login.
Dim sh, fso, here
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)

' don't start a second copy if port 8000 is already taken
Dim probe
probe = sh.Run("cmd /c netstat -ano | findstr "":8000 "" | findstr LISTENING", 0, True)
If probe = 0 Then WScript.Quit

sh.CurrentDirectory = here & "\backend"
sh.Run """" & here & "\backend\.venv\Scripts\python.exe"" -m uvicorn main:app --host 127.0.0.1 --port 8000", 0, False
