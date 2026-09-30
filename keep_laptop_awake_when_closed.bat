@echo off
title Configure Laptop to Stay Awake When Lid is Closed
cd /d "%~dp0"

echo ======================================================================
echo   🌸 Kazumi 24/7 Laptop Power Configuration
echo ======================================================================
echo.
echo By default, Windows puts your laptop to SLEEP when you close the lid,
echo which shuts off your Wi-Fi and disconnects Kazumi from Discord.
echo.
echo Setting "When I close the lid" -^> "Do nothing":
echo • Plugged in (Charger): DO NOTHING (Stays 100%% online)
echo • On Battery:           DO NOTHING (Stays 100%% online)
echo.

:: Standard Subgroup & Setting GUIDs for Power Buttons & Lid Action
powercfg /setacvalueindex SCHEME_CURRENT 4f971e89-eebd-4455-a8de-9e59040e7347 5ca83367-6e45-459f-a27b-476b1d01c936 0 >nul 2>&1
powercfg /setdcvalueindex SCHEME_CURRENT 4f971e89-eebd-4455-a8de-9e59040e7347 5ca83367-6e45-459f-a27b-476b1d01c936 0 >nul 2>&1
powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0 >nul 2>&1
powercfg /setdcvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0 >nul 2>&1
powercfg /setactive SCHEME_CURRENT

echo [✓] SUCCESS! Your laptop is now configured to STAY ONLINE when the lid is closed.
echo     Closing the lid will only turn off your screen, while Kazumi continues
echo     chatting and staying online 24/7 in the background!
echo.
echo (You can change this anytime in Windows Settings:
echo  Control Panel -^> Power Options -^> Choose what closing the lid does).
echo.
pause
