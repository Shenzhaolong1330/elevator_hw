#!/usr/bin/env bash
# 智能电梯调度系统 - Linux无头模式（纯算法）
set -e

echo "===================================="
echo "智能电梯调度算法 - 无头模式"
echo "===================================="
echo

# 查找Python命令
python_cmd="$(command -v python3 || command -v python || true)"
if [ -z "$python_cmd" ]; then
  echo "[错误] 未找到python或python3，请先安装Python 3.8+"
  exit 1
fi

echo "[1/2] 检查Python版本..."
$python_cmd --version

echo "[2/2] 安装依赖包..."
$python_cmd -m pip install --quiet elevator-py 2>/dev/null || \
  $python_cmd -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple/ elevator-py

echo "[3/3] 启动算法控制器..."
export ELEVATOR_CLIENT_TYPE=algorithm
$python_cmd algorithm_only.py
