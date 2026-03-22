@echo off
REM ============================================================
REM  check-sanity.bat  —  called by start-local.bat / restart-local.bat
REM  Sets SANITY_OK=1 if all checks pass, SANITY_OK=0 on failure.
REM  %~dp0 = astra-shared\   %~dp0..\ = parent (D:\NetSim-astra\)
REM ============================================================

set SANITY_OK=1
set UI_DIR=%~dp0..\astra-ui-app

REM --- Check 1: Cesium folder present ---
if not exist "%UI_DIR%\Cesium\Build\Cesium\Cesium.js" (
    echo.
    echo [ERROR] CesiumJS library not found.
    echo         Expected: %UI_DIR%\Cesium\Build\Cesium\Cesium.js
    echo.
    echo         Fix: Copy the Cesium build folder into astra-ui-app\Cesium\
    echo         or run:  xcopy /E /Y D:\SelfCode\Satellite\Cesium "%UI_DIR%\Cesium\"
    echo.
    set SANITY_OK=0
    goto :sanity_done
)
echo [OK] Cesium folder found.

REM --- Check 2: CESIUM_TOKEN env var ---
if not "%CESIUM_TOKEN%"=="" (
    echo [OK] CESIUM_TOKEN set via environment variable.
    goto :sanity_done
)

REM --- Check 3: CESIUM_TOKEN in settings_private.py ---
python "%~dp0check_cesium_token.py" 2>nul
if errorlevel 1 (
    echo.
    echo [WARN] No Cesium Ion token configured.
    echo        The 3D globe will load with default Bing imagery only.
    echo        To fix: edit %UI_DIR%\settings_private.py
    echo        and set CESIUM_TOKEN = "your-token"
    echo        Get a free token at https://cesium.com/ion/tokens
    echo.
    REM This is a warning only — do not set SANITY_OK=0
)

:sanity_done
