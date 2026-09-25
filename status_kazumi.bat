@echo off
title Kazumi Discord Bot Status
cd /d "%~dp0"
echo ========================================================
echo   🌸 Checking Kazumi Discord Bot Status...
echo ========================================================
powershell -Command "$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*discord_bot.py*' }; if ($procs) { Write-Host ' [●] Kazumi Discord Bot is ONLINE and RUNNING!' -ForegroundColor Green; Write-Host ('     PID: ' + ($procs.ProcessId -join ', ')); } else { Write-Host ' [○] Kazumi Discord Bot is currently OFFLINE.' -ForegroundColor Yellow; Write-Host '     Double click run_kazumi_bot.bat or launch_kazumi_silent.vbs to start.' }"
echo.
pause
