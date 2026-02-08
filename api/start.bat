@echo off
echo ========================================
echo Starting ArmourIQ Backend API Server
echo ========================================
echo.

cd /d "%~dp0"

echo Checking Python installation...
python --version
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

echo.
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Starting server on http://localhost:5001
echo Press Ctrl+C to stop
echo.

python server.py
