@echo off
REM Install Weather Notifier as a Windows Scheduled Task
REM Runs daily at 7:00 AM

echo ================================================
echo Weather Notifier - Task Scheduler Setup
echo ================================================
echo.

REM Get the directory where this script is located
set SCRIPT_DIR=%~dp0

REM Find Python path
for /f "delims=" %%i in ('where python') do set PYTHON_PATH=%%i
if "%PYTHON_PATH%"=="" (
    echo ERROR: Python not found in PATH
    echo Please install Python and add it to your PATH
    pause
    exit /b 1
)

echo Python found at: %PYTHON_PATH%
echo Script directory: %SCRIPT_DIR%
echo.

REM Install requirements
echo Installing Python dependencies...
pip install -r "%SCRIPT_DIR%requirements.txt" --quiet
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo Dependencies installed successfully.
echo.

REM Create the scheduled task
echo Creating scheduled task "WeatherNotifier"...

schtasks /create /tn "WeatherNotifier" ^
    /tr "\"%PYTHON_PATH%\" \"%SCRIPT_DIR%weather_notifier.py\"" ^
    /sc daily ^
    /st 06:40 ^
    /rl HIGHEST ^
    /f

if %errorlevel% neq 0 (
    echo ERROR: Failed to create scheduled task
    echo Try running this script as Administrator
    pause
    exit /b 1
)

echo.
echo Creating shoulder season freeze check task (4:15 PM)...

schtasks /create /tn "WeatherNotifier-ShoulderFreeze" ^
    /tr "\"%PYTHON_PATH%\" \"%SCRIPT_DIR%weather_notifier.py\" --shoulder-freeze" ^
    /sc daily ^
    /st 16:15 ^
    /rl HIGHEST ^
    /f

if %errorlevel% neq 0 (
    echo WARNING: Failed to create shoulder freeze task
    echo This is optional - main task still created
)

echo.
echo ================================================
echo SUCCESS! Weather Notifier has been scheduled.
echo ================================================
echo.
echo Tasks Created:
echo   1. WeatherNotifier - Daily at 6:40 AM (all checks)
echo   2. WeatherNotifier-ShoulderFreeze - Daily at 4:15 PM (March/Nov freeze only)
echo.
echo To test now, run:
echo   python "%SCRIPT_DIR%weather_notifier.py" --test-api
echo   python "%SCRIPT_DIR%weather_notifier.py" --test-notify
echo   python "%SCRIPT_DIR%weather_notifier.py" --shoulder-freeze --dry-run
echo.
echo To view/modify the tasks, open Task Scheduler (taskschd.msc)
echo.
pause
