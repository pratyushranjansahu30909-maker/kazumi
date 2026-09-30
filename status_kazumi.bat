@echo off
title Kazumi Discord Bot Status
cd /d "%~dp0"
echo ======================================================================
echo   🌸 Kazumi Discord Bot — Live Health and Status Check
echo ======================================================================
echo.

powershell -NoProfile -Command ^
  "$botProcs = Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*discord_bot.py*' }; " ^
  "$superProcs = Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'cmd.exe' -and $_.CommandLine -like '*kazumi_supervisor.bat*' }; " ^
  "$startupFile = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\KazumiCompanionBot.lnk'; " ^
  "if ($botProcs) { " ^
  "    Write-Host '  [●] Kazumi Discord Bot: ONLINE & RUNNING 🌸' -ForegroundColor Green; " ^
  "    foreach ($p in $botProcs) { " ^
  "        $memMb = [math]::Round((Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue).WorkingSet64 / 1MB, 1); " ^
  "        Write-Host ('      PID: ' + $p.ProcessId + ' | Memory: ' + $memMb + ' MB | Started: ' + $p.CreationDate); " ^
  "    } " ^
  "} else { " ^
  "    Write-Host '  [○] Kazumi Discord Bot: OFFLINE 💤' -ForegroundColor Red; " ^
  "    Write-Host '      Start her with launch_kazumi_silent.vbs or run_kazumi_bot.bat'; " ^
  "} " ^
  "Write-Host ''; " ^
  "if ($superProcs) { " ^
  "    Write-Host '  [●] 24/7 Watchdog Supervisor: ACTIVE & MONITORING' -ForegroundColor Green; " ^
  "} else { " ^
  "    Write-Host '  [○] 24/7 Watchdog Supervisor: INACTIVE' -ForegroundColor Gray; " ^
  "} " ^
  "Write-Host ''; " ^
  "if (Test-Path $startupFile) { " ^
  "    Write-Host '  [✓] Windows Boot Auto-Start: INSTALLED & ENABLED' -ForegroundColor Green; " ^
  "} else { " ^
  "    Write-Host '  [!] Windows Boot Auto-Start: NOT INSTALLED' -ForegroundColor Yellow; " ^
  "    Write-Host '      Run install_kazumi_autostart.bat to keep her online across PC restarts!'; " ^
  "}"

echo.
echo ======================================================================
echo   Quick Actions:
echo   • Start Silently:     launch_kazumi_silent.vbs
echo   • Install Auto-Start: install_kazumi_autostart.bat
echo   • Stop Bot:           stop_kazumi.bat
echo ======================================================================
echo.
pause
