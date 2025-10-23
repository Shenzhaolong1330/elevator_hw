#!/usr/bin/env bash
set -euo pipefail

# Navigate to the directory of the script
cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)/"

echo "项目目录: $PROJECT_DIR"

echo "安装依赖（可能需要 sudo / 使用虚拟环境）..."
python -m pip install --upgrade pip || true
pip install numpy flask requests flask_cors || echo "pip install 部分依赖失败，继续启动"

mkdir -p "$PROJECT_DIR/logs"

# 可选：启动 elevator_saga 模拟器（如需要，请取消下一行注释）
# nohup python -m elevator_saga.server.simulator > "$PROJECT_DIR/logs/simulator.log" 2>&1 & echo $! > "$PROJECT_DIR/logs/simulator.pid" && sleep 2

echo "启动后端服务（elevator_backend_flask.py）..."
nohup python "$PROJECT_DIR/elevator_backend_flask.py" > "$PROJECT_DIR/logs/backend.log" 2>&1 &
echo $! > "$PROJECT_DIR/logs/backend.pid"
sleep 2

echo "启动电梯调度器（elevator_planner.py）..."
nohup python "$PROJECT_DIR/elevator_planner.py" > "$PROJECT_DIR/logs/planner.log" 2>&1 &
echo $! > "$PROJECT_DIR/logs/planner.pid"
sleep 1

echo "已在无界面模式(headless)启动组件。日志目录：$PROJECT_DIR/logs"
echo
echo "PID:"
echo "  backend: $(cat "$PROJECT_DIR/logs/backend.pid" 2>/dev/null || echo 'n/a')"
echo "  planner: $(cat "$PROJECT_DIR/logs/planner.pid" 2>/dev/null || echo 'n/a')"
echo
echo "查看日志： tail -f $PROJECT_DIR/logs/backend.log"
echo "停止示例： kill \$(cat \"$PROJECT_DIR/logs/planner.pid\") && kill \$(cat \"$PROJECT_DIR/logs/backend.pid\")"