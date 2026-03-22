@echo off
echo Stopping NetSim Astra services...

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

echo All services stopped.
