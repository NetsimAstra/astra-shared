@echo off
echo ============================================================
echo  NetSim Astra — Local Stack Startup
echo ============================================================

REM --- Sanity checks ---
call "%~dp0check-sanity.bat"
if "%SANITY_OK%"=="0" (
    echo [ABORT] Fix the errors above then re-run this script.
    pause
    exit /b 1
)

REM --- Start services ---
echo Starting Constellation Engine on :8020 ...
start "Constellation" cmd /k "cd /d "%~dp0..\astra-constellation-engine" && python app.py"

echo Starting Radio Engine on :8010 ...
start "Radio" cmd /k "cd /d "%~dp0..\astra-radio-engine" && python app.py"

echo Starting UI App on :8000 ...
start "UI" cmd /k "cd /d "%~dp0..\astra-ui-app" && set DEV_AUTH_BYPASS=1 && set FLASK_SECRET=dev-secret && set USE_ENGINE_HTTP=1 && set RADIO_ENGINE_URL=http://localhost:8010 && set CONSTELLATION_ENGINE_URL=http://localhost:8020 && python satellite_planner.py"

echo.
echo All services starting in separate windows.
echo Open http://localhost:8000 in your browser.
echo.
echo Health checks:
echo   curl http://localhost:8010/health
echo   curl http://localhost:8020/health
echo   curl http://localhost:8000/
