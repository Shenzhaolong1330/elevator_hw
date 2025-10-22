@echo off
chcp 65001 >nul

REM Set project root directory
set PROJECT_DIR=%~dp0

REM Step 1: Install dependencies
echo Installing project dependencies...
pip install numpy flask requests flask_cors
if %errorlevel% neq 0 (
    echo Dependency installation might be incomplete, but will try to continue...
)

REM Step 2: Start key components


REM Wait a bit to ensure services have time to initialize
ping -n 3 127.0.0.1 >nul

REM Start Flask backend service
start "Flask Backend Service" cmd /k "chcp 65001 && python "%PROJECT_DIR%elevator_backend_flask.py""

REM Wait a bit
ping -n 3 127.0.0.1 >nul

REM Start elevator scheduler
start "Elevator Scheduler" cmd /k "chcp 65001 && python "%PROJECT_DIR%elevator_planner.py""
@REM start "Elevator Scheduler" cmd /k "chcp 65001 && python "%PROJECT_DIR%elevator_bus_modified_optimized.py""

REM 注意：不打开前端 UI（headless），因此没有打开 HTML 文件的步骤

echo System components have been started in headless mode!
pause
