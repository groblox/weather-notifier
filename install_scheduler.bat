@echo off
REM Install Weather Notifier as a Windows Scheduled Task
REM Reads schedule times from .env if available.

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

REM Read schedule times from .env (with defaults)
set "MORNING_TIME=06:40"
set "AFTERNOON_TIME=16:15"
if exist "%SCRIPT_DIR%.env" (
    for /f "usebackq tokens=1,* delims==" %%a in ("%SCRIPT_DIR%.env") do (
        if "%%a"=="SCHEDULE_MORNING" set "MORNING_TIME=%%b"
        if "%%a"=="SCHEDULE_AFTERNOON" set "AFTERNOON_TIME=%%b"
    )
)

REM Create the scheduled task
echo Creating scheduled task "WeatherNotifier" at %MORNING_TIME%...

schtasks /create /tn "WeatherNotifier" ^
    /tr "\"%PYTHON_PATH%\" \"%SCRIPT_DIR%weather_notifier.py\"" ^
    /sc daily ^
    /st %MORNING_TIME% ^
    /rl HIGHEST ^
    /f

if %errorlevel% neq 0 (
    echo ERROR: Failed to create scheduled task
    echo Try running this script as Administrator
    pause
    exit /b 1
)

echo.
echo Creating shoulder season freeze check task at %AFTERNOON_TIME%...

schtasks /create /tn "WeatherNotifier-ShoulderFreeze" ^
    /tr "\"%PYTHON_PATH%\" \"%SCRIPT_DIR%weather_notifier.py\" --shoulder-freeze" ^
    /sc daily ^
    /st %AFTERNOON_TIME% ^
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
echo   1. WeatherNotifier - Daily at %MORNING_TIME% (all checks)
echo   2. WeatherNotifier-ShoulderFreeze - Daily at %AFTERNOON_TIME% (March/Nov freeze only)
echo.
echo To test now, run:
echo   python "%SCRIPT_DIR%weather_notifier.py" --test-api
echo   python "%SCRIPT_DIR%weather_notifier.py" --test-notify
echo   python "%SCRIPT_DIR%weather_notifier.py" --dry-run
echo.
echo To view/modify the tasks, open Task Scheduler (taskschd.msc)
echo.
pause
