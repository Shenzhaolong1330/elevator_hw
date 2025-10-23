#!/usr/bin/env python3
"""
集成式电梯调度可视化系统 - PyQt6版本
简化版本：只保留终端输出
"""
import sys
import threading
import time
from typing import Dict, List, Set
from collections import defaultdict
import re

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, QTextEdit, 
                            QGroupBox, QGridLayout, QScrollArea, QFrame)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor, QPalette, QPainter

# 导入电梯调度算法
from elevator_saga.client.base_controller import ElevatorController
from elevator_saga.client.proxy_models import ProxyElevator, ProxyFloor, ProxyPassenger
from elevator_saga.core.models import Direction, SimulationEvent


class ElevatorSignal(QObject):
    """用于线程间通信的信号"""
    update_signal = pyqtSignal(str)
    elevator_update = pyqtSignal(dict)
    request_update = pyqtSignal(dict)


class ElevatorWidget(QWidget):
    """单个电梯的可视化组件"""
    
    def __init__(self, elevator_id, max_floors=10):
        super().__init__()
        self.elevator_id = elevator_id
        self.max_floors = max_floors
        self.current_floor = 0
        self.direction = "up"
        self.state = "resting"
        self.passenger_count = 0
        self.target_floors = []
        self.setup_ui()
        
    def setup_ui(self):
        """设置电梯UI"""
        self.setFixedSize(120, 400)
        self.setStyleSheet("background-color: #f0f0f0; border: 2px solid #ccc; border-radius: 8px;")
        
    def paintEvent(self, event):
        """绘制电梯状态"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 绘制电梯背景
        painter.fillRect(self.rect(), QColor(240, 240, 240))
        
        # 绘制楼层标记
        self.draw_floors(painter)
        
        # 绘制电梯轿厢
        self.draw_elevator_car(painter)
        
        # 绘制状态信息
        self.draw_status_info(painter)
        
    def draw_floors(self, painter):
        """绘制楼层标记"""
        floor_height = self.height() / self.max_floors
        painter.setPen(QColor(200, 200, 200))
        
        for i in range(self.max_floors + 1):
            y = int(self.height() - (i * floor_height) - 1)
            painter.drawLine(10, y, self.width() - 10, y)
            
            # 楼层数字
            painter.setPen(QColor(100, 100, 100))
            painter.drawText(5, y - 2, f"F{i}")
            painter.setPen(QColor(200, 200, 200))
    
    def draw_elevator_car(self, painter):
        """绘制电梯轿厢"""
        floor_height = self.height() / self.max_floors
        car_y = int(self.height() - (self.current_floor * floor_height) - floor_height)
        
        # 根据状态选择颜色
        if self.state == "resting":
            color = QColor(100, 200, 100)  # 绿色 - 休息
        elif self.state == "scanning":
            color = QColor(70, 130, 180)   # 蓝色 - 工作中
        else:
            color = QColor(200, 100, 100)  # 红色 - 其他状态
            
        # 绘制轿厢
        car_height = int(floor_height - 10)
        painter.fillRect(30, car_y + 5, 60, car_height, color)
        
        # 轿厢边框
        painter.setPen(QColor(50, 50, 50))
        painter.drawRect(30, car_y + 5, 60, car_height)
        
        # 电梯ID和乘客数
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(35, car_y + 25, f"E{self.elevator_id}")
        painter.drawText(35, car_y + 45, f"{self.passenger_count}人")
        
        # 方向指示器
        if self.direction == "up":
            painter.drawText(80, car_y + 25, "↑")
        else:
            painter.drawText(80, car_y + 25, "↓")
    
    def draw_status_info(self, painter):
        """绘制状态信息"""
        painter.setPen(QColor(0, 0, 0))
        
        # 状态文本
        status_text = f"状态: {self.state}"
        painter.drawText(10, 15, status_text)
        
        # 目标楼层
        targets_text = f"目标: {self.target_floors}" if self.target_floors else "目标: 无"
        painter.drawText(10, 30, targets_text)
    
    def update_state(self, state_data):
        """更新电梯状态"""
        self.current_floor = state_data.get('current_floor', 0)
        self.direction = state_data.get('direction', 'up')
        self.state = state_data.get('state', 'resting')
        self.passenger_count = state_data.get('passenger_count', 0)
        self.target_floors = state_data.get('target_floors', [])
        self.update()


class FloorRequestWidget(QWidget):
    """楼层请求可视化组件"""
    
    def __init__(self, max_floors=10):
        super().__init__()
        self.max_floors = max_floors
        self.up_requests = set()
        self.down_requests = set()
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI"""
        self.setFixedSize(80, 400)
        
    def paintEvent(self, event):
        """绘制楼层请求"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 背景
        painter.fillRect(self.rect(), QColor(250, 250, 250))
        
        floor_height = self.height() / self.max_floors
        
        for i in range(self.max_floors + 1):
            y = int(self.height() - (i * floor_height) - 1)
            
            # 楼层数字
            painter.setPen(QColor(100, 100, 100))
            painter.drawText(5, y - 2, f"F{i}")
            
            # 上行请求
            if i in self.up_requests:
                painter.setPen(QColor(255, 100, 100))
                painter.drawText(40, y - 2, "↑")
                
            # 下行请求
            if i in self.down_requests:
                painter.setPen(QColor(100, 100, 255))
                painter.drawText(60, y - 2, "↓")
    
    def update_requests(self, up_requests, down_requests):
        """更新请求状态"""
        self.up_requests = up_requests
        self.down_requests = down_requests
        self.update()


class TerminalOutputWidget(QTextEdit):
    """终端风格输出组件"""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        """设置终端样式"""
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 9))
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        
    def append_message(self, message):
        """添加消息到终端"""
        # 添加时间戳
        timestamp = time.strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        # 限制最大行数
        max_lines = 200
        lines = self.toPlainText().split('\n')
        if len(lines) > max_lines:
            self.setPlainText('\n'.join(lines[-max_lines:]))
            
        self.append(formatted_message)
        
        # 自动滚动到底部
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


class VisualizableElevatorController(ElevatorController):
    """
    支持可视化的电梯控制器
    """
    
    def __init__(self, server_url: str = "http://127.0.0.1:8000", debug: bool = False, signals=None):
        super().__init__(server_url, debug)
        self.elevator_directions: Dict[int, str] = {}
        self.elevator_target_floors: Dict[int, Set[int]] = {}
        self.passenger_destinations: Dict[int, Dict[int, int]] = {}
        self.max_floor = 0
        self.floor_requests: Dict[str, Set[int]] = {"up": set(), "down": set()}
        self.elevator_resting_floors: Dict[int, int] = {}
        self.elevator_states: Dict[int, str] = {}
        self.signals = signals
        self.actual_elevator_count = 0

    def on_init(self, elevators: List[ProxyElevator], floors: List[ProxyFloor]) -> None:
        """初始化"""
        print(" 智能SCAN电梯算法初始化 - 可视化版本")
        print(f"   管理 {len(elevators)} 部电梯")
        print(f"   服务 {len(floors)} 层楼")
        
        # 记录实际电梯数量
        self.actual_elevator_count = len(elevators)
        
        # 获取最大楼层数
        self.max_floor = len(floors) - 1
        
        # 初始化每个电梯的状态
        for i, elevator in enumerate(elevators):
            self.elevator_directions[elevator.id] = "up"
            self.elevator_target_floors[elevator.id] = set()
            self.passenger_destinations[elevator.id] = {}
            self.elevator_states[elevator.id] = 'resting'
            
            # 计算初始休息楼层
            resting_floor = self._calculate_resting_floor(i, len(elevators))
            self.elevator_resting_floors[elevator.id] = resting_floor
            
            # 移动到初始休息楼层
            elevator.go_to_floor(resting_floor, immediate=True)
            print(f"   电梯 E{elevator.id} 初始休息位置: F{resting_floor}")
            
            # 发送初始电梯状态
            if self.signals:
                elevator_data = {
                    'id': elevator.id,
                    'current_floor': elevator.current_floor,
                    'direction': self.elevator_directions[elevator.id],
                    'state': self.elevator_states[elevator.id],
                    'passenger_count': len(elevator.passengers),
                    'target_floors': list(self.elevator_target_floors[elevator.id])
                }
                self.signals.elevator_update.emit(elevator_data)
        
        if self.signals:
            self.signals.update_signal.emit(" 智能SCAN电梯算法初始化 - 可视化版本")
            self.signals.update_signal.emit(f"   管理 {self.actual_elevator_count} 部电梯")
            self.signals.update_signal.emit(f"   服务 {self.max_floor + 1} 层楼")
            for i, elevator in enumerate(elevators):
                resting_floor = self._calculate_resting_floor(i, len(elevators))
                self.signals.update_signal.emit(f"   电梯 E{elevator.id} 初始休息位置: F{resting_floor}")

    def _calculate_resting_floor(self, elevator_index: int, total_elevators: int) -> int:
        """计算休息楼层"""
        if total_elevators == 1:
            return self.max_floor // 2
        segment_size = (self.max_floor + 1) / total_elevators
        return min(int(elevator_index * segment_size + segment_size / 2), self.max_floor)

    def on_passenger_call(self, passenger: ProxyPassenger, floor: ProxyFloor, direction: str) -> None:
        """乘客呼叫回调"""
        print(f" 乘客 {passenger.id} 在 F{floor.floor} 请求 {direction} 方向")
        self.floor_requests[direction].add(floor.floor)
        print(f"   当前请求 - 上行: {sorted(self.floor_requests['up'])}, 下行: {sorted(self.floor_requests['down'])}")
        
        # 智能选择电梯响应请求
        self._smart_assign_elevator(floor.floor, direction)
        
        if self.signals:
            self.signals.update_signal.emit(f" 乘客 {passenger.id} 在 F{floor.floor} 请求 {direction} 方向")
            self.signals.update_signal.emit(f"   当前请求 - 上行: {sorted(self.floor_requests['up'])}, 下行: {sorted(self.floor_requests['down'])}")

    def _smart_assign_elevator(self, request_floor: int, direction: str) -> None:
        """智能分配电梯"""
        # 首先寻找休息电梯
        resting_elevators = []
        for elevator in self.elevators:
            if self.elevator_states[elevator.id] == 'resting':
                distance = abs(elevator.current_floor - request_floor)
                resting_elevators.append((distance, elevator.id, elevator))
        
        if resting_elevators:
            # 使用最近的休息电梯
            resting_elevators.sort(key=lambda x: x[0])
            closest_distance, closest_id, closest_elevator = resting_elevators[0]
            print(f"    唤醒休息电梯 E{closest_id} 处理 F{request_floor} 的请求 (距离: {closest_distance}层)")
            self._wake_up_elevator(closest_elevator, request_floor, direction)
            return
        
        # 没有休息电梯时，寻找可以响应的工作中空载电梯
        working_candidate = self._find_working_elevator_candidate(request_floor, direction)
        if working_candidate:
            benefit, elevator_id, elevator = working_candidate
            print(f"    智能响应: E{elevator_id} 响应 F{request_floor} 的请求 (顺路接人)")
            self._redirect_elevator(elevator, request_floor, direction)
            return
        
        print(f"    无合适电梯可用，等待扫描中的电梯自然处理请求")

    def _find_working_elevator_candidate(self, request_floor: int, direction: str):
        """寻找工作电梯候选"""
        best_candidate = None
        best_benefit = 0
        
        for elevator in self.elevators:
            elevator_id = elevator.id
            
            # 只考虑工作中的空载电梯
            if not (self.elevator_states[elevator_id] == 'scanning' and 
                   len(elevator.passengers) == 0 and 
                   len(self.elevator_target_floors[elevator_id]) > 0):
                continue
            
            current_floor = elevator.current_floor
            current_direction = self.elevator_directions[elevator_id]
            current_targets = self.elevator_target_floors[elevator_id]
            
            if not current_targets:
                continue
                
            # 获取当前主要目标
            current_target = min(current_targets) if current_direction == 'up' else max(current_targets)
            
            # 检查响应条件
            direction_ok = self._is_direction_matching(current_floor, request_floor, current_direction)
            on_the_way = self._is_on_the_way(current_floor, current_target, request_floor, current_direction)
            
            if direction_ok and on_the_way:
                distance_to_target = abs(current_floor - current_target)
                distance_to_request = abs(current_floor - request_floor)
                benefit = distance_to_target - distance_to_request
                
                if benefit > best_benefit:
                    best_benefit = benefit
                    best_candidate = (benefit, elevator_id, elevator)
        
        return best_candidate

    def _is_direction_matching(self, current_floor: int, request_floor: int, current_direction: str) -> bool:
        """检查方向匹配"""
        if current_direction == "up":
            return request_floor >= current_floor
        else:
            return request_floor <= current_floor

    def _is_on_the_way(self, current_floor: int, current_target: int, request_floor: int, direction: str) -> bool:
        """检查是否在路径上"""
        if direction == "up":
            return current_floor <= request_floor <= current_target
        else:
            return current_floor >= request_floor >= current_target

    def _redirect_elevator(self, elevator: ProxyElevator, request_floor: int, direction: str) -> None:
        """重定向电梯"""
        elevator_id = elevator.id
        self.elevator_target_floors[elevator_id].add(request_floor)
        print(f"    E{elevator_id} 将响应 F{request_floor} 的请求")

    def _wake_up_elevator(self, elevator: ProxyElevator, request_floor: int, direction: str) -> None:
        """唤醒电梯"""
        elevator_id = elevator.id
        self.elevator_states[elevator_id] = 'scanning'
        
        if request_floor > elevator.current_floor:
            self.elevator_directions[elevator_id] = 'up'
        elif request_floor < elevator.current_floor:
            self.elevator_directions[elevator_id] = 'down'
        else:
            self.elevator_directions[elevator_id] = direction
        
        elevator.go_to_floor(request_floor)
        self.elevator_target_floors[elevator_id].add(request_floor)

    def on_elevator_stopped(self, elevator: ProxyElevator, floor: ProxyFloor) -> None:
        """电梯停靠回调"""
        print(f" 电梯 E{elevator.id} 停靠在 F{floor.floor}")
        
        current_floor = floor.floor
        direction = self.elevator_directions[elevator.id]
        
        # 从目标集合中移除当前楼层
        if current_floor in self.elevator_target_floors[elevator.id]:
            self.elevator_target_floors[elevator.id].remove(current_floor)
        
        # 从全局请求中移除当前楼层的同方向请求
        if current_floor in self.floor_requests[direction]:
            self.floor_requests[direction].remove(current_floor)
            print(f"   移除 {direction} 方向在 F{current_floor} 的请求")
        
        if self.signals:
            self.signals.update_signal.emit(f" 电梯 E{elevator.id} 停靠在 F{floor.floor}")
            
            # 更新电梯状态
            elevator_data = {
                'id': elevator.id,
                'current_floor': elevator.current_floor,
                'direction': self.elevator_directions[elevator.id],
                'state': self.elevator_states[elevator.id],
                'passenger_count': len(elevator.passengers),
                'target_floors': list(self.elevator_target_floors[elevator.id])
            }
            self.signals.elevator_update.emit(elevator_data)
        
        # 检查是否还有任务
        if self._has_pending_requests() or self._has_internal_requests(elevator):
            self.elevator_states[elevator.id] = 'scanning'
            self._assign_next_floor(elevator)
        else:
            print(f"    电梯 E{elevator.id} 完成所有任务，在 F{current_floor} 进入休息状态")
            self.elevator_states[elevator.id] = 'resting'
            if self.signals:
                self.signals.update_signal.emit(f" 电梯 E{elevator.id} 进入休息状态")

    def _has_pending_requests(self) -> bool:
        """检查未处理请求"""
        return bool(self.floor_requests["up"] or self.floor_requests["down"])

    def _has_internal_requests(self, elevator: ProxyElevator) -> bool:
        """检查内部请求"""
        return bool(self.passenger_destinations[elevator.id])

    def _assign_next_floor(self, elevator: ProxyElevator) -> None:
        """分配下一个楼层"""
        current_floor = elevator.current_floor
        direction = self.elevator_directions[elevator.id]
        
        target_floors = self._get_floors_in_direction(elevator, direction)
        
        if target_floors:
            if direction == "up":
                next_floor = min(target_floors)
            else:
                next_floor = max(target_floors)
            
            print(f"   SCAN决策: E{elevator.id} {direction}方向 -> F{next_floor}")
            elevator.go_to_floor(next_floor)
            self.elevator_target_floors[elevator.id].add(next_floor)
        else:
            new_direction = "down" if direction == "up" else "up"
            print(f"   SCAN决策: E{elevator.id} 改变方向 {direction} -> {new_direction}")
            self.elevator_directions[elevator.id] = new_direction
            
            new_target_floors = self._get_floors_in_direction(elevator, new_direction)
            if new_target_floors:
                if new_direction == "up":
                    next_floor = min(new_target_floors)
                else:
                    next_floor = max(new_target_floors)
                
                print(f"   SCAN决策: E{elevator.id} {new_direction}方向 -> F{next_floor}")
                elevator.go_to_floor(next_floor)
                self.elevator_target_floors[elevator.id].add(next_floor)
            else:
                print(f"     电梯 E{elevator.id} 无任务可执行")
                self.elevator_states[elevator.id] = 'resting'

    def _get_floors_in_direction(self, elevator: ProxyElevator, direction: str) -> Set[int]:
        """获取方向上的楼层"""
        current_floor = elevator.current_floor
        target_floors = set()
        
        # 内部选层请求
        elevator_id = elevator.id
        for passenger_id, destination in self.passenger_destinations[elevator_id].items():
            if ((direction == "up" and destination > current_floor) or
                (direction == "down" and destination < current_floor)):
                target_floors.add(destination)
        
        # 外部呼叫请求
        if direction == "up":
            for floor_num in self.floor_requests["up"] | self.floor_requests["down"]:
                if floor_num > current_floor:
                    target_floors.add(floor_num)
        else:
            for floor_num in self.floor_requests["up"] | self.floor_requests["down"]:
                if floor_num < current_floor:
                    target_floors.add(floor_num)
        
        return target_floors

    def on_passenger_board(self, elevator: ProxyElevator, passenger: ProxyPassenger) -> None:
        """乘客上梯回调"""
        print(f"    乘客{passenger.id} 上 E{elevator.id} (F{elevator.current_floor} -> F{passenger.destination})")
        self.passenger_destinations[elevator.id][passenger.id] = passenger.destination
        
        if self.elevator_states[elevator.id] == 'resting':
            self.elevator_states[elevator.id] = 'scanning'
            print(f"    电梯 E{elevator.id} 因乘客上梯而激活")
        
        if self.signals:
            self.signals.update_signal.emit(f"    乘客{passenger.id} 上 E{elevator.id} (F{elevator.current_floor} -> F{passenger.destination})")

    def on_passenger_alight(self, elevator: ProxyElevator, passenger: ProxyPassenger, floor: ProxyFloor) -> None:
        """乘客下梯回调"""
        print(f"    乘客{passenger.id} 下 E{elevator.id} 在 F{floor.floor}")
        if passenger.id in self.passenger_destinations[elevator.id]:
            del self.passenger_destinations[elevator.id][passenger.id]
        
        if self.signals:
            self.signals.update_signal.emit(f"    乘客{passenger.id} 下 E{elevator.id} 在 F{floor.floor}")

    def on_elevator_idle(self, elevator: ProxyElevator) -> None:
        """电梯空闲回调"""
        print(f" 电梯 E{elevator.id} 在 F{elevator.current_floor} 层空闲")
        
        self.elevator_target_floors[elevator.id].clear()
        
        if self._has_pending_requests() or self._has_internal_requests(elevator):
            self.elevator_states[elevator.id] = 'scanning'
            self._assign_next_floor(elevator)
        else:
            self.elevator_states[elevator.id] = 'resting'
            print(f"    电梯 E{elevator.id} 停在 F{elevator.current_floor} 休息")
            
            if self.signals:
                self.signals.update_signal.emit(f" 电梯 E{elevator.id} 进入休息状态")

    # 其他必要的回调方法
    def on_event_execute_start(self, tick: int, events: List[SimulationEvent], elevators: List[ProxyElevator], floors: List[ProxyFloor]) -> None:
        pass

    def on_event_execute_end(self, tick: int, events: List[SimulationEvent], elevators: List[ProxyElevator], floors: List[ProxyFloor]) -> None:
        pass

    def on_elevator_passing_floor(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        pass

    def on_elevator_approaching(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        pass

    def on_elevator_move(self, elevator: ProxyElevator, from_position: float, to_position: float, direction: str, status: str) -> None:
        pass


class ElevatorVisualization(QMainWindow):
    """电梯调度可视化主窗口"""
    
    def __init__(self):
        super().__init__()
        self.signals = ElevatorSignal()
        self.elevator_widgets = {}
        self.elevator_controller = None
        self.actual_elevator_count = 2
        self.setup_ui()
        self.setup_connections()
        self.simulation_thread = None
        
    def setup_ui(self):
        """设置用户界面"""
        self.setWindowTitle("智能SCAN电梯调度算法可视化 - PyQt6")
        self.setGeometry(100, 100, 1400, 900)
        
        # 中央窗口
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 上部：电梯状态面板
        elevator_panel = self.create_elevator_panel()
        main_layout.addWidget(elevator_panel, 3)
        
        # 下部：控制面板和终端输出
        bottom_panel = self.create_bottom_panel()
        main_layout.addWidget(bottom_panel, 2)
        
    def create_elevator_panel(self):
        """创建电梯状态面板"""
        panel = QGroupBox("电梯状态监控")
        layout = QHBoxLayout(panel)
        
        # 请求面板
        request_frame = QFrame()
        request_frame.setFrameStyle(QFrame.Shape.Box)
        request_layout = QVBoxLayout(request_frame)
        
        request_label = QLabel("楼层请求")
        request_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        request_layout.addWidget(request_label)
        
        self.request_widget = FloorRequestWidget()
        request_layout.addWidget(self.request_widget)
        
        layout.addWidget(request_frame)
        
        # 电梯面板 - 动态创建电梯组件
        self.elevators_frame = QFrame()
        self.elevators_layout = QHBoxLayout(self.elevators_frame)
        layout.addWidget(self.elevators_frame)
        
        return panel
        
    def create_bottom_panel(self):
        """创建底部面板"""
        panel = QWidget()
        layout = QHBoxLayout(panel)
        
        # 左侧：控制面板
        left_panel = self.create_control_panel()
        layout.addWidget(left_panel, 1)
        
        # 右侧：终端输出
        right_panel = self.create_terminal_panel()
        layout.addWidget(right_panel, 2)
        
        return panel
        
    def create_control_panel(self):
        """创建控制面板"""
        panel = QGroupBox("控制面板")
        layout = QVBoxLayout(panel)
        
        # 控制按钮
        control_layout = QVBoxLayout()
        
        self.start_btn = QPushButton("开始模拟")
        self.pause_btn = QPushButton("暂停")
        self.reset_btn = QPushButton("重置")
        
        self.start_btn.setStyleSheet("""
            QPushButton { 
                background-color: #4CAF50; 
                color: white; 
                font-size: 14px;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        self.pause_btn.setStyleSheet("""
            QPushButton { 
                background-color: #ff9800; 
                color: white; 
                font-size: 14px;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #e68900;
            }
        """)
        
        self.reset_btn.setStyleSheet("""
            QPushButton { 
                background-color: #f44336; 
                color: white; 
                font-size: 14px;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.pause_btn)
        control_layout.addWidget(self.reset_btn)
        
        # 添加弹性空间使按钮居中
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
        
        return panel
        
    def create_terminal_panel(self):
        """创建终端输出面板"""
        panel = QGroupBox("终端输出")
        layout = QVBoxLayout(panel)
        
        self.terminal_output = TerminalOutputWidget()
        layout.addWidget(self.terminal_output)
        
        return panel
    
    def setup_connections(self):
        """设置信号连接"""
        self.start_btn.clicked.connect(self.start_simulation)
        self.pause_btn.clicked.connect(self.pause_simulation)
        self.reset_btn.clicked.connect(self.reset_simulation)
        
        # 连接更新信号
        self.signals.update_signal.connect(self.update_terminal)
        self.signals.elevator_update.connect(self.update_elevator_display)
        self.signals.request_update.connect(self.update_request_display)
    
    def create_elevator_widgets(self, count):
        """动态创建电梯组件"""
        # 清除现有组件
        for i in reversed(range(self.elevators_layout.count())): 
            self.elevators_layout.itemAt(i).widget().setParent(None)
        
        self.elevator_widgets = {}
        for i in range(count):
            elevator_widget = ElevatorWidget(i)
            self.elevator_widgets[i] = elevator_widget
            self.elevators_layout.addWidget(elevator_widget)
    
    def start_simulation(self):
        """开始模拟"""
        self.terminal_output.append_message("🚀 开始电梯调度模拟...")
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        
        # 创建电梯控制器
        self.elevator_controller = VisualizableElevatorController(
            server_url="http://127.0.0.1:8000",
            debug=True,
            signals=self.signals
        )
        
        # 先创建2部电梯的显示（默认）
        self.create_elevator_widgets(2)
        
        # 在新线程中运行电梯算法
        self.simulation_thread = threading.Thread(target=self.run_elevator_algorithm)
        self.simulation_thread.daemon = True
        self.simulation_thread.start()
    
    def pause_simulation(self):
        """暂停模拟"""
        self.terminal_output.append_message(" 模拟暂停")
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
    
    def reset_simulation(self):
        """重置模拟"""
        self.terminal_output.append_message(" 重置模拟")
        self.terminal_output.clear()
        
        # 重置电梯状态
        for elevator_id, widget in self.elevator_widgets.items():
            widget.update_state({
                'current_floor': 0,
                'direction': 'up',
                'state': 'resting',
                'passenger_count': 0,
                'target_floors': []
            })
        
        # 重置请求显示
        self.request_widget.update_requests(set(), set())
    
    def run_elevator_algorithm(self):
        """运行电梯算法（在线程中）"""
        try:
            if self.elevator_controller:
                self.elevator_controller.start()
            else:
                self.signals.update_signal.emit(" 未设置电梯控制器")
        except Exception as e:
            self.signals.update_signal.emit(f" 模拟错误: {str(e)}")
    
    def update_terminal(self, message):
        """更新终端输出"""
        self.terminal_output.append_message(message)
        
        # 检测电梯数量信息
        if "系统检测到" in message and "部电梯" in message:
            try:
                count = int(message.split(" ")[-2])  # 提取数字
                if count != len(self.elevator_widgets):
                    self.create_elevator_widgets(count)
                    self.terminal_output.append_message(f" 已更新显示为 {count} 部电梯")
            except:
                pass
    
    def update_elevator_display(self, elevator_data):
        """更新电梯显示"""
        elevator_id = elevator_data.get('id')
        if elevator_id in self.elevator_widgets:
            self.elevator_widgets[elevator_id].update_state(elevator_data)
    
    def update_request_display(self, request_data):
        """更新请求显示"""
        up_requests = request_data.get('up_requests', set())
        down_requests = request_data.get('down_requests', set())
        self.request_widget.update_requests(up_requests, down_requests)


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 创建可视化界面
    window = ElevatorVisualization()
    window.show()
    
    # 启动应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()