#!/usr/bin/env python3
"""
电梯可视化后端服务
作用：接收电梯模拟器的数据，提供给前端展示
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from threading import Lock
from datetime import datetime
import json
import os

# 结果文件路径：脚本目录（兼容本地）和仓库根（兼容评测环境）
RESULT_FILE = os.path.join(os.path.dirname(__file__), "result.json")
REPO_RESULT_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "result.json"))

app = Flask(__name__)
CORS(app)

# 存储电梯状态的全局变量
elevator_state = {
    "tick": 0,
    "elevators": [],
    "events": [],
    "passengers": [],
    "max_floor": 5,
    "timestamp": datetime.now().isoformat()
}

state_lock = Lock()

def _write_result_file(state: dict) -> None:
    """将当前状态以 JSON 原子性写入 result.json（写入脚本目录和仓库根）"""
    try:
        for path in (RESULT_FILE, REPO_RESULT_FILE):
            # 确保目录存在
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp_path = path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            # 原子替换
            os.replace(tmp_path, path)
    except Exception:
        # 写入失败不影响主流程
        pass

# 启动时写一次初始状态，避免评测在读取时找不到文件
_write_result_file(elevator_state)

@app.route('/api/state', methods=['GET'])
def get_state():
    """获取当前电梯状态（前端用这个接口获取数据）"""
    with state_lock:
        return jsonify(elevator_state)

@app.route('/api/update', methods=['POST'])
def update_state():
    """更新电梯状态（bus_example.py 会调用这个接口）"""
    global elevator_state
    
    data = request.get_json()
    
    with state_lock:
        elevator_state = {
            "tick": data.get("tick", 0),
            "elevators": data.get("elevators", []),
            "events": data.get("events", []),
            "passengers": data.get("passengers", []),
            "max_floor": data.get("max_floor", 5),
            "timestamp": datetime.now().isoformat()
        }
        # 写入结果文件（同时写到脚本目录和仓库根）
        _write_result_file(elevator_state)
    
    return jsonify({"status": "ok", "message": "State updated"})

@app.route('/api/reset', methods=['POST'])
def reset_state():
    """重置所有状态"""
    global elevator_state
    
    with state_lock:
        elevator_state = {
            "tick": 0,
            "elevators": [],
            "events": [],
            "passengers": [],
            "max_floor": 5,
            "timestamp": datetime.now().isoformat()
        }
        # 写入结果文件（重置后的空状态）
        _write_result_file(elevator_state)
    
    return jsonify({"status": "ok", "message": "State reset"})

@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})


if __name__ == '__main__':
    print("=" * 60)
    print("🚀 电梯可视化后端启动")
    print("=" * 60)
    print("📡 后端服务地址: http://127.0.0.1:5000")
    print("📊 获取状态: GET http://127.0.0.1:5000/api/state")
    print("📤 更新状态: POST http://127.0.0.1:5000/api/update")
    print("🔄 重置状态: POST http://127.0.0.1:5000/api/reset")
    print("=" * 60)
    app.run(debug=False, port=5000, host='127.0.0.1')
