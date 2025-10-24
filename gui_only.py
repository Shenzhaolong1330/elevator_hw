#!/usr/bin/env python3
"""
现代化电梯监控系统 - 纯GUI模式
只负责显示，不控制电梯逻辑
"""
import sys
import os
from typing import List

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import pyqtSignal

from elevator_saga.client.base_controller import ElevatorController
from elevator_saga.client.proxy_models import ProxyElevator, ProxyFloor, ProxyPassenger

# 导入原有的GUI组件
from gui import (
    ElevatorMonitorSystem, SignalBridge, 
    ElevatorCard, CallIndicatorPanel, ModernLogViewer
)


class GUIOnlyController(ElevatorController):
    """
    纯GUI控制器 - 只接收事件用于显示，不发送控制指令
    设置环境变量 ELEVATOR_CLIENT_TYPE=gui 时使用
    """
    
    def __init__(self, server_url: str = "http://127.0.0.1:8000", debug: bool = False, signals=None):
        super().__init__(server_url, debug)
        self.signals = signals
        
        # 状态管理（仅用于显示）
        self.unit_state = {}
        self.unit_heading = {}
        self.pending_calls = {"up": set(), "down": set()}
        self.total_levels = 0
        
        # 统计数据
        self.stats = {
            'total_calls': 0,
            'completed_trips': 0,
            'total_wait_time': 0,
            'wait_count': 0,
            'avg_wait_time': 0,
        }
        
        self._emit_log("GUI模式启动 - 只显示不控制", "success")

    def on_init(self, elevators: List[ProxyElevator], floors: List[ProxyFloor]) -> None:
        """初始化 - 仅记录信息"""
        self.total_levels = len(floors) - 1
        self._emit_log(f"系统连接 | {len(elevators)}台电梯 | {len(floors)}层楼", "success")
        
        for idx, unit in enumerate(elevators):
            self.unit_state[unit.id] = "idle"
            self.unit_heading[unit.id] = "none"
            self._emit_log(f"电梯{idx + 1} 已连接", "info")
            self._emit_unit_status(unit)

    def on_passenger_call(self, passenger: ProxyPassenger, floor: ProxyFloor, direction: str) -> None:
        """呼叫事件 - 仅显示"""
        self.pending_calls[direction].add(floor.floor)
        self.stats['total_calls'] += 1
        self._emit_log(f"新呼叫 @ F{floor.floor} → {direction}", "warning")
        self._emit_call_status()
        # 不调用任何 go_to_floor 或电梯控制指令

    def on_elevator_move(self, elevator: ProxyElevator, from_pos: float, to_pos: float, 
                        direction: str, status: str) -> None:
        """电梯移动 - 更新显示"""
        self.unit_heading[elevator.id] = direction if direction else "none"
        self.unit_state[elevator.id] = status if status else "moving"
        self._emit_unit_status(elevator)

    def on_elevator_stopped(self, elevator: ProxyElevator, floor: ProxyFloor) -> None:
        """电梯停止 - 更新显示"""
        heading = self.unit_heading[elevator.id]
        if heading in self.pending_calls:
            self.pending_calls[heading].discard(floor.floor)
            self._emit_call_status()
        
        self.unit_state[elevator.id] = "loading"
        self._emit_log(f"电梯{elevator.id + 1} 停靠 @ F{floor.floor}", "success")
        self._emit_unit_status(elevator)

    def on_passenger_board(self, elevator: ProxyElevator, passenger: ProxyPassenger) -> None:
        """乘客登梯 - 更新统计"""
        self.stats['completed_trips'] += 1
        
        # 计算等待时间（如果有时间戳信息）
        if hasattr(passenger, 'call_time') and hasattr(passenger, 'board_time'):
            wait_time = passenger.board_time - passenger.call_time
            self.stats['total_wait_time'] += wait_time
            self.stats['wait_count'] += 1
            self.stats['avg_wait_time'] = self.stats['total_wait_time'] / self.stats['wait_count']
        
        self._emit_log(f"乘客登梯{elevator.id + 1} → F{passenger.destination}", "info")
        self._emit_unit_status(elevator)
        self._emit_stats()

    def on_passenger_alight(self, elevator: ProxyElevator, passenger: ProxyPassenger, floor: ProxyFloor) -> None:
        """乘客离梯"""
        self._emit_unit_status(elevator)

    def on_elevator_idle(self, elevator: ProxyElevator) -> None:
        """电梯空闲"""
        self.unit_state[elevator.id] = "idle"
        self.unit_heading[elevator.id] = "none"
        self._emit_unit_status(elevator)

    def on_elevator_passing_floor(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        """经过楼层"""
        pass

    def on_elevator_approaching(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        """接近楼层"""
        pass

    def on_event_execute_start(self, tick, events, elevators, floors):
        """事件执行开始"""
        pass
    
    def on_event_execute_end(self, tick, events, elevators, floors):
        """事件执行结束"""
        pass

    def _emit_log(self, message, level='info'):
        """发送日志"""
        if self.signals:
            self.signals.log_message.emit(message, level)

    def _emit_unit_status(self, unit):
        """发送电梯状态"""
        if self.signals:
            # 收集目标楼层（从乘客目的地）
            targets = []
            if hasattr(unit, 'passengers'):
                targets = list(set(p.destination for p in unit.passengers if hasattr(p, 'destination')))
            
            data = {
                'id': unit.id,
                'current_level': unit.current_floor,
                'heading': self.unit_heading[unit.id],
                'status': self.unit_state[unit.id],
                'load_count': len(unit.passengers) if hasattr(unit, 'passengers') else 0,
                'targets': targets
            }
            self.signals.unit_status.emit(data)

    def _emit_call_status(self):
        """发送呼叫状态"""
        if self.signals:
            data = {
                'up_calls': self.pending_calls["up"],
                'down_calls': self.pending_calls["down"]
            }
            self.signals.call_status.emit(data)

    def _emit_stats(self):
        """发送统计数据"""
        if self.signals and hasattr(self.signals, 'stats_update'):
            self.signals.stats_update.emit(self.stats)


class GUIMonitorSystem(ElevatorMonitorSystem):
    """
    GUI监控系统 - 适配纯显示模式
    """
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("智能电梯监控系统 - GUI模式")
        
    def start_simulation(self):
        """启动模拟 - 使用GUI专用控制器"""
        self.log_viewer.append_log("GUI模式启动 - 等待算法连接...", "success")
        self.start_btn.setEnabled(False)
        
        # 创建GUI专用控制器
        self.controller = GUIOnlyController(
            server_url="http://127.0.0.1:8000",
            debug=True,
            signals=self.signals
        )
        
        # 创建默认电梯卡片（会根据实际连接数量调整）
        self.create_unit_cards(4)
        
        # 启动模拟线程
        import threading
        self.sim_thread = threading.Thread(target=self.run_simulation)
        self.sim_thread.daemon = True
        self.sim_thread.start()


def main():
    """主函数"""
    # 设置环境变量
    os.environ['ELEVATOR_CLIENT_TYPE'] = 'gui'
    
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle('Fusion')
    
    window = GUIMonitorSystem()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
