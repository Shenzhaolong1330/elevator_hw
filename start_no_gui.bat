
@echo off
REM 智能电梯调度系统 - Windows无头模式（纯算法）
chcp 65001 >nul

echo ====================================
echo 智能电梯调度算法 - 无头模式
echo ====================================
echo.

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

echo [1/2] 检查依赖包...
python -m pip install --quiet elevator-py 2>nul
if errorlevel 1 (
    echo [警告] 使用国内镜像源重试...
    python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple/ elevator-py
)

echo [2/2] 启动算法控制器...
set ELEVATOR_CLIENT_TYPE=algorithm
python algorithm_only.py

if errorlevel 1 (
    echo.
    echo [错误] 算法启动失败
    pause
)