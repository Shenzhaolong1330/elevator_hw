#!/usr/bin/env python3
"""
现代化电梯监控系统 - 全新UI设计
采用扁平化设计风格，卡片式布局，动画效果
"""
import sys
import threading
from typing import Dict, List, Set
from collections import defaultdict

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, QTextEdit, 
                            QGroupBox, QGridLayout, QFrame, QSplitter)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QFont, QColor, QPalette, QPainter, QLinearGradient, QPen, QBrush

from elevator_saga.client.base_controller import ElevatorController
from elevator_saga.client.proxy_models import ProxyElevator, ProxyFloor, ProxyPassenger
from elevator_saga.core.models import Direction, SimulationEvent


class SignalBridge(QObject):
    """信号桥接器"""
    log_message = pyqtSignal(str, str)  # message, level
    unit_status = pyqtSignal(dict)
    call_status = pyqtSignal(dict)


class ElevatorCard(QWidget):
    """电梯卡片组件 - 现代扁平化设计"""
    
    def __init__(self, unit_id, max_levels=10):
        super().__init__()
        self.unit_id = unit_id
        self.max_levels = max_levels
        self.current_level = 0
        self.heading = "none"
        self.status = "idle"
        self.load_count = 0
        self.targets = []
        self.animation_progress = 0
        self.setup_ui()
        
        # 动画定时器
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.update_animation)
        self.anim_timer.start(50)
        
    def setup_ui(self):
        """设置UI"""
        self.setFixedSize(180, 450)
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f5f5f5);
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }
        """)
        
    def paintEvent(self, event):
        """绘制电梯卡片"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 绘制背景
        self._draw_background(painter)
        
        # 绘制标题
        self._draw_header(painter)
        
        # 绘制电梯井
        self._draw_shaft(painter)
        
        # 绘制电梯轿厢
        self._draw_cabin(painter)
        
        # 绘制信息面板
        self._draw_info_panel(painter)
        
    def _draw_background(self, painter):
        """绘制背景"""
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(255, 255, 255))
        gradient.setColorAt(1, QColor(245, 245, 245))
        painter.fillRect(self.rect(), gradient)
        
    def _draw_header(self, painter):
        """绘制标题区"""
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(66, 133, 244))
        painter.drawRoundedRect(0, 0, self.width(), 50, 12, 12)
        
        # 电梯编号
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        painter.drawText(20, 30, f"电梯 {self.unit_id + 1}")
        
        # 状态指示灯
        status_colors = {
            "idle": QColor(76, 175, 80),
            "moving": QColor(33, 150, 243),
            "loading": QColor(255, 152, 0)
        }
        painter.setBrush(status_colors.get(self.status, QColor(158, 158, 158)))
        painter.drawEllipse(self.width() - 35, 15, 20, 20)
        
    def _draw_shaft(self, painter):
        """绘制电梯井道"""
        shaft_x = 40
        shaft_y = 70
        shaft_width = 100
        shaft_height = 300
        
        # 井道背景
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(240, 240, 240))
        painter.drawRoundedRect(shaft_x, shaft_y, shaft_width, shaft_height, 8, 8)
        
        # 绘制楼层线
        level_height = shaft_height / self.max_levels
        painter.setPen(QPen(QColor(220, 220, 220), 1))
        
        for i in range(self.max_levels + 1):
            y = int(shaft_y + shaft_height - (i * level_height))
            painter.drawLine(shaft_x, y, shaft_x + shaft_width, y)
            
            # 楼层标签
            painter.setPen(QColor(120, 120, 120))
            painter.setFont(QFont("Arial", 8))
            painter.drawText(shaft_x - 25, y + 4, f"F{i}")
            
            # 目标楼层标记
            if i in self.targets:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(255, 193, 7, 150))
                painter.drawEllipse(shaft_x + shaft_width + 5, y - 4, 8, 8)
        
    def _draw_cabin(self, painter):
        """绘制电梯轿厢"""
        shaft_x = 40
        shaft_y = 70
        shaft_height = 300
        
        level_height = shaft_height / self.max_levels
        cabin_y = int(shaft_y + shaft_height - (self.current_level * level_height) - level_height + 5)
        cabin_height = int(level_height - 10)
        
        # 轿厢阴影
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 30))
        painter.drawRoundedRect(45, cabin_y + 3, 90, cabin_height, 6, 6)
        
        # 轿厢主体 - 根据状态变色
        cabin_colors = {
            "idle": QColor(76, 175, 80),
            "moving": QColor(33, 150, 243),
            "loading": QColor(255, 152, 0)
        }
        gradient = QLinearGradient(45, cabin_y, 45, cabin_y + cabin_height)
        base_color = cabin_colors.get(self.status, QColor(158, 158, 158))
        gradient.setColorAt(0, base_color.lighter(120))
        gradient.setColorAt(1, base_color)
        painter.setBrush(gradient)
        painter.drawRoundedRect(45, cabin_y, 90, cabin_height, 6, 6)
        
        # 轿厢边框
        painter.setPen(QPen(base_color.darker(120), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(45, cabin_y, 90, cabin_height, 6, 6)
        
        # 电梯编号
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        text_y = cabin_y + cabin_height // 2 - 8
        painter.drawText(50, text_y, 80, 20, Qt.AlignmentFlag.AlignCenter, f"E{self.unit_id + 1}")
        
        # 乘客数量
        painter.setFont(QFont("Arial", 9))
        painter.drawText(50, text_y + 18, 80, 20, Qt.AlignmentFlag.AlignCenter, f"👥 {self.load_count}")
        
        # 方向指示器
        if self.heading == "up":
            self._draw_arrow(painter, 90, cabin_y - 15, True)
        elif self.heading == "down":
            self._draw_arrow(painter, 90, cabin_y + cabin_height + 5, False)
    
    def _draw_arrow(self, painter, x, y, is_up):
        """绘制方向箭头"""
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(244, 67, 54) if is_up else QColor(33, 150, 243))
        
        if is_up:
            points = [
                (x, y),
                (x - 6, y + 8),
                (x + 6, y + 8)
            ]
        else:
            points = [
                (x, y + 8),
                (x - 6, y),
                (x + 6, y)
            ]
        
        from PyQt6.QtCore import QPointF
        painter.drawPolygon([QPointF(px, py) for px, py in points])
    
    def _draw_info_panel(self, painter):
        """绘制信息面板"""
        panel_y = 390
        
        # 状态文本
        status_text = {
            "idle": "空闲待机",
            "moving": "运行中",
            "loading": "装载中"
        }
        
        painter.setPen(QColor(80, 80, 80))
        painter.setFont(QFont("Arial", 9))
        painter.drawText(20, panel_y, f"状态: {status_text.get(self.status, '未知')}")
        
        painter.drawText(20, panel_y + 20, f"楼层: F{self.current_level}")
        
        # 目标楼层
        if self.targets:
            target_str = ", ".join([f"F{t}" for t in sorted(self.targets)[:3]])
            if len(self.targets) > 3:
                target_str += "..."
            painter.drawText(20, panel_y + 40, f"目标: {target_str}")
        else:
            painter.drawText(20, panel_y + 40, "目标: 无")
    
    def update_animation(self):
        """更新动画"""
        self.animation_progress = (self.animation_progress + 1) % 100
        if self.status == "moving":
            self.update()
    
    def update_state(self, state_data):
        """更新状态"""
        self.current_level = state_data.get('current_level', 0)
        self.heading = state_data.get('heading', 'none')
        self.status = state_data.get('status', 'idle')
        self.load_count = state_data.get('load_count', 0)
        self.targets = state_data.get('targets', [])
        self.update()


class CallIndicatorPanel(QWidget):
    """呼叫指示面板"""
    
    def __init__(self, max_levels=10):
        super().__init__()
        self.max_levels = max_levels
        self.up_calls = set()
        self.down_calls = set()
        self.setFixedWidth(120)
        
    def paintEvent(self, event):
        """绘制呼叫指示"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 标题
        painter.setPen(QColor(80, 80, 80))
        painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        painter.drawText(10, 25, "呼叫信号")
        
        # 绘制楼层呼叫
        level_height = (self.height() - 50) / self.max_levels
        
        for i in range(self.max_levels + 1):
            y = int(self.height() - 20 - (i * level_height))
            
            # 楼层标签
            painter.setPen(QColor(120, 120, 120))
            painter.setFont(QFont("Arial", 8))
            painter.drawText(10, y + 4, f"F{i}")
            
            # 上行呼叫
            if i in self.up_calls:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(244, 67, 54))
                painter.drawEllipse(50, y - 4, 12, 12)
                painter.setPen(QColor(255, 255, 255))
                painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
                painter.drawText(50, y - 4, 12, 12, Qt.AlignmentFlag.AlignCenter, "↑")
            
            # 下行呼叫
            if i in self.down_calls:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(33, 150, 243))
                painter.drawEllipse(75, y - 4, 12, 12)
                painter.setPen(QColor(255, 255, 255))
                painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
                painter.drawText(75, y - 4, 12, 12, Qt.AlignmentFlag.AlignCenter, "↓")
    
    def update_calls(self, up_calls, down_calls):
        """更新呼叫状态"""
        self.up_calls = up_calls
        self.down_calls = down_calls
        self.update()


class ModernLogViewer(QTextEdit):
    """现代日志查看器"""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.log_colors = {
            'info': '#2196F3',
            'success': '#4CAF50',
            'warning': '#FF9800',
            'error': '#F44336'
        }
        
    def setup_ui(self):
        """设置UI样式"""
        self.setReadOnly(True)
        self.setFont(QFont("Courier New", 9))
        self.setStyleSheet("""
            QTextEdit {
                background-color: #263238;
                color: #ECEFF1;
                border: none;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        
    def append_log(self, message, level='info'):
        """添加日志"""
        import time
        timestamp = time.strftime("%H:%M:%S")
        color = self.log_colors.get(level, '#ECEFF1')
        
        html = f'<span style="color: #78909C;">[{timestamp}]</span> '
        html += f'<span style="color: {color};">{message}</span>'
        
        self.append(html)
        
        # 限制行数
        doc = self.document()
        if doc.lineCount() > 300:
            cursor = self.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor, 50)
            cursor.removeSelectedText()
        
        # 滚动到底部
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


class StatisticsPanel(QWidget):
    """统计面板"""
    
    def __init__(self):
        super().__init__()
        self.stats = {
            'total_calls': 0,
            'completed_trips': 0,
            'avg_wait_time': 0,
            'efficiency': 100
        }
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI"""
        layout = QGridLayout(self)
        layout.setSpacing(15)
        
        # 创建统计卡片
        self.create_stat_card(layout, "总呼叫", "total_calls", 0, 0, "#2196F3")
        self.create_stat_card(layout, "完成行程", "completed_trips", 0, 1, "#4CAF50")
        self.create_stat_card(layout, "平均等待", "avg_wait_time", 1, 0, "#FF9800")
        self.create_stat_card(layout, "运行效率", "efficiency", 1, 1, "#9C27B0")
        
    def create_stat_card(self, layout, title, key, row, col, color):
        """创建统计卡片"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {color}, stop:1 {QColor(color).lighter(120).name()});
                border-radius: 10px;
                padding: 15px;
            }}
        """)
        card.setFixedHeight(100)
        
        card_layout = QVBoxLayout(card)
        
        # 标题
        title_label = QLabel(title)
        title_label.setStyleSheet("color: white; font-size: 12px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 数值
        value_label = QLabel("0")
        value_label.setStyleSheet("color: white; font-size: 28px; font-weight: bold;")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setObjectName(key)
        
        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        
        layout.addWidget(card, row, col)
        
    def update_stats(self, stats):
        """更新统计数据"""
        self.stats.update(stats)
        for key, value in stats.items():
            label = self.findChild(QLabel, key)
            if label:
                if key == 'avg_wait_time':
                    label.setText(f"{value:.1f}s")
                elif key == 'efficiency':
                    label.setText(f"{value}%")
                else:
                    label.setText(str(value))


class VisualizationController(ElevatorController):
    """可视化电梯控制器"""
    
    def __init__(self, server_url: str = "http://127.0.0.1:8000", debug: bool = False, signals=None):
        super().__init__(server_url, debug)
        self.signals = signals
        
        # 状态管理
        self.unit_state = {}
        self.unit_heading = {}
        self.service_queue = {}
        self.passenger_registry = {}
        self.pending_calls = {"up": set(), "down": set()}
        
        self.total_levels = 0
        self.unit_capacity = 10
        self.zone_assignment = {}
        
        # 统计
        self.stats = {
            'total_calls': 0,
            'completed_trips': 0,
            'avg_wait_time': 0,
            'efficiency': 100
        }

    def on_init(self, elevators: List[ProxyElevator], floors: List[ProxyFloor]) -> None:
        """初始化"""
        self.total_levels = len(floors) - 1
        self._emit_log(f"系统启动 | {len(elevators)}台电梯 | {len(floors)}层楼", "success")
        
        for idx, unit in enumerate(elevators):
            self.unit_state[unit.id] = "idle"
            self.unit_heading[unit.id] = "none"
            self.service_queue[unit.id] = []
            self.passenger_registry[unit.id] = {}
            
            home_level = self._calculate_home_position(idx, len(elevators))
            self.zone_assignment[unit.id] = self._get_service_zone(idx, len(elevators))
            
            unit.go_to_floor(home_level, immediate=True)
            self._emit_log(f"电梯{idx + 1} 初始化 @ F{home_level}", "info")
            
            # 发送初始状态
            self._emit_unit_status(unit)

    def _calculate_home_position(self, index: int, total: int) -> int:
        """计算初始位置"""
        if total == 1:
            return self.total_levels // 2
        segment = (self.total_levels + 1) / total
        return min(int(index * segment + segment / 2), self.total_levels)

    def _get_service_zone(self, index: int, total: int) -> tuple:
        """获取服务区域"""
        if total == 1:
            return (0, self.total_levels)
        zone_size = (self.total_levels + 1) / total
        start = int(index * zone_size)
        end = int((index + 1) * zone_size) if index < total - 1 else self.total_levels
        return (start, end)

    def on_passenger_call(self, passenger: ProxyPassenger, floor: ProxyFloor, direction: str) -> None:
        """处理呼叫"""
        self.pending_calls[direction].add(floor.floor)
        self.stats['total_calls'] += 1
        
        self._emit_log(f"新呼叫 @ F{floor.floor} → {direction}", "warning")
        self._emit_call_status()
        
        # 智能分配
        self._intelligent_dispatch(floor.floor, direction)

    def _intelligent_dispatch(self, target_floor: int, direction: str):
        """智能派遣"""
        candidates = []
        
        for unit in self.elevators:
            score = self._calculate_score(unit, target_floor, direction)
            if score > 0:
                candidates.append((score, unit.id, unit))
        
        if candidates:
            candidates.sort(reverse=True)
            _, best_id, best_unit = candidates[0]
            self._assign_task(best_unit, target_floor)
            self._emit_log(f"分配电梯{best_id + 1} 响应 F{target_floor}", "info")

    def _calculate_score(self, unit: ProxyElevator, target_floor: int, direction: str) -> float:
        """计算分配评分"""
        score = 0.0
        state = self.unit_state[unit.id]
        
        if state == "idle":
            distance = abs(unit.current_floor - target_floor)
            score = 100 - distance
            
            zone_start, zone_end = self.zone_assignment[unit.id]
            if zone_start <= target_floor <= zone_end:
                score += 50
        
        elif state == "moving":
            heading = self.unit_heading[unit.id]
            if heading == direction:
                if (heading == "up" and unit.current_floor < target_floor) or \
                   (heading == "down" and unit.current_floor > target_floor):
                    score = 80 - abs(unit.current_floor - target_floor)
                    load_factor = len(unit.passengers) / self.unit_capacity
                    score *= (1 - load_factor * 0.5)
        
        return score

    def _assign_task(self, unit: ProxyElevator, target_floor: int):
        """分配任务"""
        if target_floor not in self.service_queue[unit.id]:
            self.service_queue[unit.id].append(target_floor)
        
        if self.unit_state[unit.id] == "idle":
            self.unit_state[unit.id] = "moving"
            self._execute_next(unit)

    def _execute_next(self, unit: ProxyElevator):
        """执行下一任务"""
        queue = self.service_queue[unit.id]
        if not queue:
            self.unit_state[unit.id] = "idle"
            self.unit_heading[unit.id] = "none"
            self._emit_unit_status(unit)
            return
        
        current = unit.current_floor
        heading = self.unit_heading[unit.id]
        
        if heading == "up" or heading == "none":
            upper = [f for f in queue if f > current]
            if upper:
                next_floor = min(upper)
                self.unit_heading[unit.id] = "up"
            else:
                lower = [f for f in queue if f < current]
                next_floor = max(lower) if lower else queue[0]
                self.unit_heading[unit.id] = "down" if lower else "none"
        else:
            lower = [f for f in queue if f < current]
            if lower:
                next_floor = max(lower)
                self.unit_heading[unit.id] = "down"
            else:
                upper = [f for f in queue if f > current]
                next_floor = min(upper) if upper else queue[0]
                self.unit_heading[unit.id] = "up" if upper else "none"
        
        unit.go_to_floor(next_floor)
        self._emit_unit_status(unit)

    def on_elevator_stopped(self, elevator: ProxyElevator, floor: ProxyFloor) -> None:
        """电梯停靠"""
        if floor.floor in self.service_queue[elevator.id]:
            self.service_queue[elevator.id].remove(floor.floor)
        
        heading = self.unit_heading[elevator.id]
        if heading in self.pending_calls:
            self.pending_calls[heading].discard(floor.floor)
            self._emit_call_status()
        
        self.unit_state[elevator.id] = "loading"
        self._emit_log(f"电梯{elevator.id + 1} 停靠 @ F{floor.floor}", "success")
        self._emit_unit_status(elevator)
        
        if self.service_queue[elevator.id] or self.passenger_registry[elevator.id]:
            self._execute_next(elevator)
        else:
            self.unit_state[elevator.id] = "idle"
            self.unit_heading[elevator.id] = "none"
            self._emit_unit_status(elevator)

    def on_passenger_board(self, elevator: ProxyElevator, passenger: ProxyPassenger) -> None:
        """乘客登梯"""
        self.passenger_registry[elevator.id][passenger.id] = passenger.destination
        
        if passenger.destination not in self.service_queue[elevator.id]:
            self.service_queue[elevator.id].append(passenger.destination)
        
        self.stats['completed_trips'] += 1
        self._emit_log(f"乘客登梯{elevator.id + 1} → F{passenger.destination}", "info")
        self._emit_unit_status(elevator)

    def on_passenger_alight(self, elevator: ProxyElevator, passenger: ProxyPassenger, floor: ProxyFloor) -> None:
        """乘客离梯"""
        if passenger.id in self.passenger_registry[elevator.id]:
            del self.passenger_registry[elevator.id][passenger.id]
        
        self._emit_unit_status(elevator)

    def on_elevator_idle(self, elevator: ProxyElevator) -> None:
        """电梯空闲"""
        self.service_queue[elevator.id].clear()
        self.unit_state[elevator.id] = "idle"
        self.unit_heading[elevator.id] = "none"
        self._emit_unit_status(elevator)

    def _emit_log(self, message, level='info'):
        """发送日志"""
        if self.signals:
            self.signals.log_message.emit(message, level)

    def _emit_unit_status(self, unit):
        """发送电梯状态"""
        if self.signals:
            data = {
                'id': unit.id,
                'current_level': unit.current_floor,
                'heading': self.unit_heading[unit.id],
                'status': self.unit_state[unit.id],
                'load_count': len(unit.passengers),
                'targets': self.service_queue[unit.id]
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

    # 必需回调
    def on_event_execute_start(self, tick, events, elevators, floors):
        pass
    
    def on_event_execute_end(self, tick, events, elevators, floors):
        pass
    
    def on_elevator_passing_floor(self, elevator, floor, direction):
        pass
    
    def on_elevator_approaching(self, elevator, floor, direction):
        pass
    
    def on_elevator_move(self, elevator, from_pos, to_pos, direction, status):
        pass


class ElevatorMonitorSystem(QMainWindow):
    """电梯监控系统主窗口"""
    
    def __init__(self):
        super().__init__()
        self.signals = SignalBridge()
        self.unit_cards = {}
        self.controller = None
        self.sim_thread = None
        self.setup_ui()
        self.connect_signals()
        
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("智能电梯监控系统")
        self.setGeometry(50, 50, 1600, 900)
        self.setStyleSheet("background-color: #FAFAFA;")
        
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # 标题栏
        header = self.create_header()
        main_layout.addWidget(header)
        
        # 内容区域
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：呼叫指示器
        self.call_panel = CallIndicatorPanel()
        content_splitter.addWidget(self.call_panel)
        
        # 中间：电梯卡片区
        self.cards_container = QWidget()
        self.cards_layout = QHBoxLayout(self.cards_container)
        self.cards_layout.setSpacing(20)
        content_splitter.addWidget(self.cards_container)
        
        # 右侧：日志和统计
        right_panel = self.create_right_panel()
        content_splitter.addWidget(right_panel)
        
        content_splitter.setStretchFactor(0, 1)
        content_splitter.setStretchFactor(1, 4)
        content_splitter.setStretchFactor(2, 2)
        
        main_layout.addWidget(content_splitter)
        
    def create_header(self):
        """创建标题栏"""
        header = QFrame()
        header.setFixedHeight(80)
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1976D2, stop:1 #2196F3);
                border-radius: 10px;
            }
        """)
        
        layout = QHBoxLayout(header)
        
        # 标题
        title = QLabel("🏢 智能电梯监控系统")
        title.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
        layout.addWidget(title)
        
        layout.addStretch()
        
        # 控制按钮
        self.start_btn = QPushButton("▶ 启动")
        self.pause_btn = QPushButton("⏸ 暂停")
        self.reset_btn = QPushButton("🔄 重置")
        
        for btn in [self.start_btn, self.pause_btn, self.reset_btn]:
            btn.setFixedSize(100, 40)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: white;
                    color: #1976D2;
                    border: none;
                    border-radius: 20px;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #E3F2FD;
                }
                QPushButton:pressed {
                    background-color: #BBDEFB;
                }
            """)
            layout.addWidget(btn)
        
        return header
    
    def create_right_panel(self):
        """创建右侧面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(15)
        
        # 统计面板
        stats_group = QGroupBox("系统统计")
        stats_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                color: #424242;
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
        """)
        stats_layout = QVBoxLayout(stats_group)
        self.stats_panel = StatisticsPanel()
        stats_layout.addWidget(self.stats_panel)
        layout.addWidget(stats_group)
        
        # 日志查看器
        log_group = QGroupBox("系统日志")
        log_group.setStyleSheet(stats_group.styleSheet())
        log_layout = QVBoxLayout(log_group)
        self.log_viewer = ModernLogViewer()
        log_layout.addWidget(self.log_viewer)
        layout.addWidget(log_group)
        
        return panel
    
    def connect_signals(self):
        """连接信号"""
        self.start_btn.clicked.connect(self.start_simulation)
        self.pause_btn.clicked.connect(self.pause_simulation)
        self.reset_btn.clicked.connect(self.reset_simulation)
        
        self.signals.log_message.connect(self.log_viewer.append_log)
        self.signals.unit_status.connect(self.update_unit_display)
        self.signals.call_status.connect(self.update_call_display)
    
    def start_simulation(self):
        """启动模拟"""
        self.log_viewer.append_log("系统启动中...", "success")
        self.start_btn.setEnabled(False)
        
        # 创建控制器
        self.controller = VisualizationController(
            server_url="http://127.0.0.1:8000",
            debug=True,
            signals=self.signals
        )
        
        # 创建默认电梯卡片
        self.create_unit_cards(2)
        
        # 启动模拟线程
        self.sim_thread = threading.Thread(target=self.run_simulation)
        self.sim_thread.daemon = True
        self.sim_thread.start()
    
    def pause_simulation(self):
        """暂停模拟"""
        self.log_viewer.append_log("系统已暂停", "warning")
    
    def reset_simulation(self):
        """重置模拟"""
        self.log_viewer.append_log("系统已重置", "info")
        self.log_viewer.clear()
        
        for card in self.unit_cards.values():
            card.update_state({
                'current_level': 0,
                'heading': 'none',
                'status': 'idle',
                'load_count': 0,
                'targets': []
            })
        
        self.call_panel.update_calls(set(), set())
    
    def create_unit_cards(self, count):
        """创建电梯卡片"""
        # 清除现有卡片
        for i in reversed(range(self.cards_layout.count())):
            self.cards_layout.itemAt(i).widget().setParent(None)
        
        self.unit_cards = {}
        for i in range(count):
            card = ElevatorCard(i)
            self.unit_cards[i] = card
            self.cards_layout.addWidget(card)
    
    def run_simulation(self):
        """运行模拟"""
        try:
            if self.controller:
                self.controller.start()
        except Exception as e:
            self.signals.log_message.emit(f"错误: {str(e)}", "error")
    
    def update_unit_display(self, data):
        """更新电梯显示"""
        unit_id = data.get('id')
        if unit_id in self.unit_cards:
            self.unit_cards[unit_id].update_state(data)
    
    def update_call_display(self, data):
        """更新呼叫显示"""
        self.call_panel.update_calls(
            data.get('up_calls', set()),
            data.get('down_calls', set())
        )

def main():
    """主函数"""
    app = QApplication(sys.argv)
    window = ElevatorMonitorSystem()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()