@echo off
REM Uninstall Weather Notifier scheduled tasks

echo ================================================
echo Weather Notifier - Remove Scheduled Tasks
echo ================================================
echo.

schtasks /delete /tn "WeatherNotifier" /f
schtasks /delete /tn "WeatherNotifier-ShoulderFreeze" /f

echo.
echo Tasks removed (if they existed).
echo.
pause
