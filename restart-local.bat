@echo off
echo ============================================================
echo  NetSim Astra — Restart Local Stack
echo ============================================================

REM --- Sanity checks ---
call "%~dp0check-sanity.bat"
if "%SANITY_OK%"=="0" (
    echo [ABORT] Fix the errors above then re-run this script.
    pause
    exit /b 1
)

REM --- Stop existing services ---
echo Stopping existing services...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 " ^| findstr LISTENING') do (
    echo Killing UI App (PID %%a)
    taskkill /F /PID %%a >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8010 " ^| findstr LISTENING') do (
    echo Killing Radio Engine (PID %%a)
    taskkill /F /PID %%a >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8020 " ^| findstr LISTENING') do (
    echo Killing Constellation Engine (PID %%a)
    taskkill /F /PID %%a >nul 2>&1
)

echo All services stopped. Waiting 2 seconds...
timeout /t 2 /nobreak >nul

REM --- Start services ---
echo Starting Constellation Engine on :8020 ...
start "Constellation" cmd /k "cd /d "%~dp0..\astra-constellation-engine" && python app.py"

echo Starting Radio Engine on :8010 ...
start "Radio" cmd /k "cd /d "%~dp0..\astra-radio-engine" && python app.py"

echo Starting UI App on :8000 ...
start "UI" cmd /k "cd /d "%~dp0..\astra-ui-app" && set DEV_AUTH_BYPASS=1 && set FLASK_SECRET=dev-secret && python satellite_planner.py"

echo.
echo All services restarted. Open http://localhost:8000
