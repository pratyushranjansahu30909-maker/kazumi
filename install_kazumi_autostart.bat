@echo off
title Install Kazumi 24/7 Auto-Start
cd /d "%~dp0"

echo ======================================================================
echo   🌸 Installing Kazumi 24/7 Background Auto-Start...
echo ======================================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "VBS_PATH=%SCRIPT_DIR%launch_kazumi_silent.vbs"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_PATH=%STARTUP_DIR%\KazumiCompanionBot.lnk"

echo [*] Creating Windows Startup Shortcut...
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; " ^
  "$sc = $ws.CreateShortcut('%SHORTCUT_PATH%'); " ^
  "$sc.TargetPath = 'wscript.exe'; " ^
  "$sc.Arguments = '\"%VBS_PATH%\"'; " ^
  "$sc.WorkingDirectory = '%SCRIPT_DIR%'; " ^
  "$sc.Description = 'Kazumi Discord Companion 24/7 Background Service'; " ^
  "$sc.WindowStyle = 7; " ^
  "$sc.Save();"

if exist "%SHORTCUT_PATH%" (
    echo [✓] Successfully installed to Windows Startup folder:
    echo     "%SHORTCUT_PATH%"
) else (
    echo [!] Warning: Could not create startup shortcut in %STARTUP_DIR%.
)

echo.
echo [*] Launching Kazumi silently in background right now...
wscript.exe "%VBS_PATH%"

powershell -Command "Start-Sleep -Seconds 3" >nul 2>&1
echo.
echo ======================================================================
echo   🌸 Kazumi is now configured to stay ALWAYS ONLINE!
echo   • She starts automatically whenever Windows boots or you log in.
echo   • Her supervisor automatically recovers and restarts her if interrupted.
echo   • Check her live status anytime with: status_kazumi.bat
echo   • Stop her anytime with:               stop_kazumi.bat
echo ======================================================================
echo.
pause
