@echo off
chcp 65001 >nul

REM Set project root directory
set PROJECT_DIR=%~dp0

REM Check if Conda is available and activate elevator environment
where conda >nul 2>&1
if %errorlevel% equ 0 (
    echo Conda detected, trying to activate elevator environment...
    call activate elevator
    if %errorlevel% neq 0 (
        echo First activation attempt failed, trying alternative command...
        call conda activate elevator
        if %errorlevel% neq 0 (
            echo Failed to activate elevator environment, will use system Python instead.
        )
    )
) else (
    echo Conda not found, will use system Python.
)

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Please install Python first.
    pause
    exit /b 1
)

REM For simplicity, use system Python directly without virtual environment
set USE_CONDA=0

REM Install necessary dependencies (simplified version, no specific versions)
echo Installing project dependencies...
pip install numpy flask requests

if %errorlevel% neq 0 (
    echo Dependencies installation might be incomplete, but will try to continue...
)

REM Start elevator_saga server
start "elevator_saga Server" cmd /k "chcp 65001 && python -m elevator_saga.server.simulator"

REM Wait 2 seconds to ensure server startup
ping -n 3 127.0.0.1 >nul

REM Start Flask backend service
start "Flask Backend Service" cmd /k "chcp 65001 && python "%PROJECT_DIR%elevator_backend_flask.py""

REM Wait 2 seconds
ping -n 3 127.0.0.1 >nul

REM Start elevator scheduler
start "Elevator Scheduler" cmd /k "chcp 65001 && python "%PROJECT_DIR%elevator_planner.py""

REM Wait 2 seconds
ping -n 3 127.0.0.1 >nul

REM Open the specific HTML frontend interface
set HTML_FILE="%PROJECT_DIR%elevator_frontend_html.html"
echo Checking if HTML file exists at: %HTML_FILE%
if exist %HTML_FILE% (
    echo HTML file found. Attempting to open in browser...
    rem 尝试多种方式打开HTML文件
    start "Elevator Dispatch System Frontend" %HTML_FILE%
    rem 如果第一种方式失败，尝试使用explorer.exe
    if %errorlevel% neq 0 (
        echo First attempt failed, trying with explorer.exe...
        explorer.exe %HTML_FILE%
    )
    rem 再检查一次是否成功打开
    if %errorlevel% neq 0 (
        echo Failed to open HTML file. Please manually open: %HTML_FILE%
    ) else (
        echo HTML frontend opened successfully.
    )
) else (
    echo Warning: HTML frontend file not found at %HTML_FILE%
    echo Checking project directory for any HTML files...
    for %%f in ("%PROJECT_DIR%"*.html) do (
        if exist "%%f" (
            echo Found alternative HTML file: %%f
            echo Attempting to open in browser...
            start "Elevator Dispatch System Frontend" "%%f"
            if %errorlevel% neq 0 (
                echo First attempt failed, trying with explorer.exe...
                explorer.exe "%%f"
            )
            goto html_opened
        )
    )
    echo Error: No HTML files found in the project directory.
    echo Please manually open the frontend HTML file.
):html_opened

REM Show startup completion information
echo.
echo ===========================================================
echo                     System Started Successfully!
echo ===========================================================
echo.
echo Started components:
echo - elevator_saga server (port: 8000)
echo - Flask backend service (port: 5000)
echo - Elevator scheduler (based on LOOK algorithm)
echo - Frontend visualization interface
echo.
echo Notes:
echo - To stop the system, close all open command windows
echo - First run may take longer, please be patient
echo ===========================================================

REM Keep current window open
pause