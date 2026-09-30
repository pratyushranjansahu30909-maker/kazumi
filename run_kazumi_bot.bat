@echo off
title Kazumi Discord Bot (Interactive Supervisor)
cd /d "%~dp0"
echo ========================================================
echo   🌸 Starting Kazumi Discord Bot Supervisor...
echo   (Press Ctrl+C to stop)
echo ========================================================

:loop
python discord_bot.py
set EXITCODE=%ERRORLEVEL%

if %EXITCODE% EQU 0 (
    echo.
    echo [🌸] Kazumi Bot finished cleanly. Restarting in 3 seconds...
    powershell -Command "Start-Sleep -Seconds 3" >nul 2>&1
    goto loop
)

echo.
echo [⚠️] Kazumi Bot process exited with code %EXITCODE%.
echo [🔄] Auto-restarting in 5 seconds to keep Kazumi online...
powershell -Command "Start-Sleep -Seconds 5" >nul 2>&1
goto loop
