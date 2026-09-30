Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "c:\Users\Lenovo\kazumi (gravity)"
' 0 = Hide window completely, False = Do not wait for script to return
WshShell.Run "cmd.exe /c kazumi_supervisor.bat", 0, False
