#!/usr/bin/env bash
set -euo pipefail

# 确保脚本在项目根目录下运行
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

echo "后台进程已启动，日志保存于 $PROJECT_DIR/logs"

# 尝试打开默认浏览器显示前端页面（兼容 xdg-open / open）
FRONTEND="$PROJECT_DIR/elevator_frontend_html.html"
if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$FRONTEND" >/dev/null 2>&1 || echo "无法通过 xdg-open 打开前端，请手动打开 $FRONTEND"
elif command -v open >/dev/null 2>&1; then
    open "$FRONTEND" >/dev/null 2>&1 || echo "无法通过 open 打开前端，请手动打开 $FRONTEND"
else
    echo "未找到打开浏览器的命令，请手动打开： $FRONTEND"
fi

echo
echo "PID:"
echo "  backend: $(cat "$PROJECT_DIR/logs/backend.pid" 2>/dev/null || echo 'n/a')"
echo "  planner: $(cat "$PROJECT_DIR/logs/planner.pid" 2>/dev/null || echo 'n/a')"
echo
echo "查看日志： tail -f $PROJECT_DIR/logs/backend.log"
echo "停止示例： kill \$(cat \"$PROJECT_DIR/logs/planner.pid\") && kill \$(cat \"$PROJECT_DIR/logs/backend.pid\")"