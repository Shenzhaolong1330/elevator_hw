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

REM Wait 2 seconds to ensure server startup
ping -n 3 127.0.0.1 >nul

REM Start Flask backend service
start "Flask Backend Service" cmd /k "chcp 65001 && python "%PROJECT_DIR%elevator_backend_flask.py""

REM Wait 2 seconds
ping -n 3 127.0.0.1 >nul

REM Start elevator scheduler
start "Elevator Scheduler" cmd /k "chcp 65001 && python "%PROJECT_DIR%elevator_planner.py""
@REM start "Elevator Scheduler" cmd /k "chcp 65001 && python "%PROJECT_DIR%elevator_bus_modified_optimized.py""

REM Open frontend HTML file
start "Elevator Frontend" "%PROJECT_DIR%elevator_frontend_html.html"

echo System components have been started successfully!
pause