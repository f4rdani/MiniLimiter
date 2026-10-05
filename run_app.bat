@echo off
setlocal
cd /d "%~dp0"

:: Check for administrative permissions
net session >nul 2>&1
if %errorLevel% == 0 (
    goto :run_app
) else (
    echo [MiniLimiter] Requesting Administrator Privileges...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

:run_app
echo [MiniLimiter] Starting with Administrator Privileges...
call .\venv\Scripts\activate.bat
python src\main.py
pause
