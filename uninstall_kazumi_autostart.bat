@echo off
title Uninstall Kazumi Auto-Start
cd /d "%~dp0"

echo ======================================================================
echo   🌸 Removing Kazumi Windows Auto-Start...
echo ======================================================================

set "SHORTCUT_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\KazumiCompanionBot.lnk"

if exist "%SHORTCUT_PATH%" (
    del /f /q "%SHORTCUT_PATH%"
    echo [✓] Removed startup shortcut from Windows Startup folder.
) else (
    echo [i] No startup shortcut was found.
)

echo.
echo Would you also like to stop any currently running Kazumi processes?
call stop_kazumi.bat
