@echo off
REM 智能电梯调度系统 - Windows启动脚本（带GUI）
chcp 65001 >nul

echo ====================================
echo 智能电梯监控系统 - GUI模式
echo ====================================
echo.

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

echo [1/3] 检查依赖包...
python -m pip install --quiet elevator-py PyQt6 2>nul
if errorlevel 1 (
    echo [警告] 使用国内镜像源重试...
    python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple/ elevator-py PyQt6
)

echo [2/3] 启动GUI...
set ELEVATOR_CLIENT_TYPE=gui
python gui_only.py

if errorlevel 1 (
    echo.
    echo [错误] GUI启动失败
    pause
)