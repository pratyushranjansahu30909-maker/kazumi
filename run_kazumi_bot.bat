@echo off
title Kazumi Discord Bot
cd /d "%~dp0"
echo ========================================================
echo   🌸 Starting Kazumi Discord Bot...
echo ========================================================
python discord_bot.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Bot exited with code %ERRORLEVEL%.
    pause
)
