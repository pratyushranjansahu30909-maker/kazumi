@echo off
setlocal enabledelayedexpansion
title Kazumi Bot Supervisor
cd /d "%~dp0"

if not exist "logs" mkdir "logs"

echo [%date% %time%] 🌸 Kazumi Supervisor started. Ensuring Kazumi stays always online... >> "logs\kazumi_supervisor.log"

:loop
echo [%date% %time%] 🌸 Launching Kazumi Discord Bot... >> "logs\kazumi_supervisor.log"
python -u discord_bot.py >> "logs\kazumi_supervisor.log" 2>&1
set EXIT_CODE=%ERRORLEVEL%

echo [%date% %time%] ⚠️ Kazumi process exited with code !EXIT_CODE!. >> "logs\kazumi_supervisor.log"

:: Avoid tight CPU spin if python fails immediately (e.g. missing interpreter or token)
echo [%date% %time%] 🔄 Auto-restarting Kazumi Discord Bot in 5 seconds... >> "logs\kazumi_supervisor.log"
powershell -Command "Start-Sleep -Seconds 5" >nul 2>&1
goto loop
