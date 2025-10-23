#!/usr/bin/env bash
set -e
"""
智能电梯调度系统 - 启动脚本（带 GUI）
"""

# 自动寻找 python 与 pip（优先 python3 / pip3）
python_cmd="$(command -v python3 || command -v python)"
if [ -z "$python_cmd" ]; then
  echo "未找到 python 或 python3，请先安装 Python。"
  exit 1
fi

pip_cmd="$(command -v pip3 || command -v pip || true)"
if [ -z "$pip_cmd" ]; then
  echo "未找到 pip，使用 python -m pip 安装依赖..."
  "$python_cmd" -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple/ elevator-py PyQt6
else
  "$pip_cmd" install -i https://pypi.tuna.tsinghua.edu.cn/simple/ elevator-py PyQt6
fi

# 启动 GUI
"$python_cmd" ./gui.py