@echo off
echo ========================================
echo ArmourIQ - Complete System Startup
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] Starting Backend API Server...
echo.
start "ArmourIQ API" cmd /k "cd api && echo Installing dependencies... && pip install -r requirements.txt && echo. && echo Starting API server on http://localhost:5001 && echo. && python server.py"

timeout /t 3 >nul

echo [2/3] Starting Frontend UI...
echo.
start "ArmourIQ Frontend" cmd /k "cd demo-ui && echo Installing dependencies... && npm install && echo. && echo Starting frontend on http://localhost:5174 && echo. && npm run dev"

echo.
echo [3/3] System Status
echo ========================================
echo Backend API:  http://localhost:5001
echo Frontend UI:  http://localhost:5174
echo ========================================
echo.
echo Both services are starting in separate windows.
echo Wait a few seconds for them to be ready.
echo.
echo Press any key to exit this window (services will continue running)
pause >nul
