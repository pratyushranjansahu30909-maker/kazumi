@echo off
title Stop Kazumi Discord Bot
cd /d "%~dp0"
echo ======================================================================
echo   🌸 Stopping Kazumi Discord Bot and Supervisor...
echo ======================================================================

powershell -NoProfile -Command ^
  "$killed = 0; " ^
  "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*kazumi_supervisor.bat*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; $killed++ }; " ^
  "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*discord_bot.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; $killed++ }; " ^
  "if ($killed -gt 0) { " ^
  "    Write-Host (' [✓] Successfully stopped ' + $killed + ' Kazumi process(es).') -ForegroundColor Green; " ^
  "} else { " ^
  "    Write-Host ' [i] No running Kazumi processes were found.' -ForegroundColor Yellow; " ^
  "}"

echo.
echo Kazumi is now stopped. (Run launch_kazumi_silent.vbs to start again anytime.)
echo.
pause
