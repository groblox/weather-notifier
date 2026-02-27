@echo off
REM ==========================================================
REM  Weather Notifier — Guided Setup
REM  Installs dependencies, configures .env, and schedules tasks.
REM ==========================================================
setlocal enabledelayedexpansion

echo.
echo  ===================================================
echo   Weather Notifier - Setup
echo  ===================================================
echo.

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"

REM ----------------------------------------------------------
REM  Step 1: Check Python
REM ----------------------------------------------------------
echo  [1/6] Checking for Python...
for /f "delims=" %%i in ('where python 2^>nul') do set "PYTHON_PATH=%%i"
if "%PYTHON_PATH%"=="" (
    echo.
    echo  ERROR: Python not found in PATH.
    echo  Please install Python 3.10+ from https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)
echo  Found: %PYTHON_PATH%
echo.

REM ----------------------------------------------------------
REM  Step 2: Install dependencies
REM ----------------------------------------------------------
echo  [2/6] Installing Python dependencies...
pip install -r "%SCRIPT_DIR%requirements.txt" --quiet
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Failed to install dependencies.
    pause
    exit /b 1
)
echo  Dependencies installed.
echo.

REM ----------------------------------------------------------
REM  Step 3: Configure API keys
REM ----------------------------------------------------------
if exist "%SCRIPT_DIR%.env" (
    echo  [3/6] Found existing .env file.
    set /p RECONFIGURE="  Reconfigure? (y/N): "
    if /i "!RECONFIGURE!" neq "y" goto :skip_env
)

echo  [3/6] Configuring API credentials...
echo.
echo  You need API keys from:
echo    - Aeris Weather: https://www.aerisweather.com/
echo    - Pushover:      https://pushover.net/
echo.

set /p AERIS_ID="  Aeris Client ID: "
set /p AERIS_SECRET="  Aeris Client Secret: "
set /p PUSH_USER="  Pushover User Key: "
set /p PUSH_TOKEN="  Pushover API Token: "
echo.

REM ----------------------------------------------------------
REM  Step 4: Station ID
REM ----------------------------------------------------------
echo  [4/6] Station configuration
set /p STATION="  PWS Station ID [pws_kalhoove43]: "
if "!STATION!"=="" set "STATION=pws_kalhoove43"
echo.

REM ----------------------------------------------------------
REM  Step 5: Schedule times
REM ----------------------------------------------------------
echo  [5/6] Schedule configuration (24-hour format HH:MM)
set /p SCHED_AM="  Morning check time [06:40]: "
if "!SCHED_AM!"=="" set "SCHED_AM=06:40"
set /p SCHED_PM="  Afternoon check time [16:15]: "
if "!SCHED_PM!"=="" set "SCHED_PM=16:15"
echo.

REM Write .env
echo # Weather Notifier Configuration> "%SCRIPT_DIR%.env"
echo.>> "%SCRIPT_DIR%.env"
echo # API Credentials>> "%SCRIPT_DIR%.env"
echo AERIS_CLIENT_ID=!AERIS_ID!>> "%SCRIPT_DIR%.env"
echo AERIS_CLIENT_SECRET=!AERIS_SECRET!>> "%SCRIPT_DIR%.env"
echo PUSHOVER_USER_KEY=!PUSH_USER!>> "%SCRIPT_DIR%.env"
echo PUSHOVER_API_TOKEN=!PUSH_TOKEN!>> "%SCRIPT_DIR%.env"
echo.>> "%SCRIPT_DIR%.env"
echo # Station>> "%SCRIPT_DIR%.env"
echo STATION_ID=!STATION!>> "%SCRIPT_DIR%.env"
echo.>> "%SCRIPT_DIR%.env"
echo # Schedule>> "%SCRIPT_DIR%.env"
echo SCHEDULE_MORNING=!SCHED_AM!>> "%SCRIPT_DIR%.env"
echo SCHEDULE_AFTERNOON=!SCHED_PM!>> "%SCRIPT_DIR%.env"
echo.>> "%SCRIPT_DIR%.env"
echo # Override any other defaults below (see .env.example for options)>> "%SCRIPT_DIR%.env"

echo  Configuration saved to .env
echo.

:skip_env

REM ----------------------------------------------------------
REM  Step 6: Read schedule from .env and register tasks
REM ----------------------------------------------------------
echo  [6/6] Registering scheduled tasks...
echo.

REM Read schedule times from .env
set "MORNING_TIME=06:40"
set "AFTERNOON_TIME=16:15"
for /f "usebackq tokens=1,* delims==" %%a in ("%SCRIPT_DIR%.env") do (
    if "%%a"=="SCHEDULE_MORNING" set "MORNING_TIME=%%b"
    if "%%a"=="SCHEDULE_AFTERNOON" set "AFTERNOON_TIME=%%b"
)

echo  Creating "WeatherNotifier" task at %MORNING_TIME%...
schtasks /create /tn "WeatherNotifier" ^
    /tr "\"%PYTHON_PATH%\" \"%SCRIPT_DIR%weather_notifier.py\"" ^
    /sc daily ^
    /st %MORNING_TIME% ^
    /rl HIGHEST ^
    /f >nul 2>&1

if %errorlevel% neq 0 (
    echo  WARNING: Failed to create morning task.
    echo  Try running this script as Administrator.
) else (
    echo  Morning task created.
)

echo  Creating "WeatherNotifier-ShoulderFreeze" task at %AFTERNOON_TIME%...
schtasks /create /tn "WeatherNotifier-ShoulderFreeze" ^
    /tr "\"%PYTHON_PATH%\" \"%SCRIPT_DIR%weather_notifier.py\" --shoulder-freeze" ^
    /sc daily ^
    /st %AFTERNOON_TIME% ^
    /rl HIGHEST ^
    /f >nul 2>&1

if %errorlevel% neq 0 (
    echo  WARNING: Failed to create afternoon task.
) else (
    echo  Afternoon task created.
)

echo.

REM ----------------------------------------------------------
REM  Verification
REM ----------------------------------------------------------
echo  ===================================================
echo   Verifying setup...
echo  ===================================================
echo.

echo  Testing API connection...
"%PYTHON_PATH%" "%SCRIPT_DIR%weather_notifier.py" --test-api
if %errorlevel% neq 0 (
    echo.
    echo  WARNING: API test failed. Check your credentials in .env
    echo.
)

echo.
set /p SEND_TEST="  Send a test push notification? (Y/n): "
if /i "!SEND_TEST!" neq "n" (
    "%PYTHON_PATH%" "%SCRIPT_DIR%weather_notifier.py" --test-notify
)

echo.
echo  ===================================================
echo   Setup Complete!
echo  ===================================================
echo.
echo  Scheduled Tasks:
echo    WeatherNotifier             - Daily at %MORNING_TIME%
echo    WeatherNotifier-ShoulderFreeze - Daily at %AFTERNOON_TIME%
echo.
echo  To run a manual check:
echo    python "%SCRIPT_DIR%weather_notifier.py" --dry-run
echo.
echo  To modify settings, edit: %SCRIPT_DIR%.env
echo  See .env.example for all available options.
echo.
pause
