@echo off

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python not found. Please install Python first.
    pause
    exit /b 1
)

REM Set environment variables
set VENV_DIR=venv
set REQUIREMENTS_FILE=requirements.txt

REM Check if virtual environment exists
if not exist %VENV_DIR% (
    echo Creating virtual environment...
    python -m venv %VENV_DIR%
    
    REM Activate virtual environment and install dependencies
    echo Installing dependencies...
    %VENV_DIR%\Scripts\pip install -r %REQUIREMENTS_FILE%
    %VENV_DIR%\Scripts\pip install elevator-py
    
    if %errorlevel% neq 0 (
        echo Error: Failed to install dependencies.
        pause
        exit /b 1
    )
)

REM Activate virtual environment
call %VENV_DIR%\Scripts\activate

REM Start GUI program and algorithm program
echo Starting Elevator Monitoring System...
start "Elevator Monitor GUI" python gui_only.py

echo Starting Elevator Scheduling Algorithm...
start "Elevator Scheduling Algorithm" python algorithm_only.py

echo Programs started successfully!
pause