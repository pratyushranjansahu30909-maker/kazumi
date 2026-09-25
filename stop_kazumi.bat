@echo off
title Stop Kazumi Discord Bot
cd /d "%~dp0"
echo ========================================================
echo   🌸 Stopping Kazumi Discord Bot...
echo ========================================================
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*discord_bot.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo.
echo [✓] Kazumi Discord Bot stopped.
pause
