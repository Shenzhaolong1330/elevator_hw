#!/usr/bin/env python3
"""
现代化电梯监控系统 - 纯GUI模式
只负责显示，不控制电梯逻辑
增强版：添加更多监控信息、统计数据和性能指标
"""
import sys
import os
import time
from datetime import datetime
from typing import List, Dict, Set, Optional

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import pyqtSignal, QObject

from elevator_saga.client.base_controller import ElevatorController
from elevator_saga.client.proxy_models import ProxyElevator, ProxyFloor, ProxyPassenger

# 导入原有的GUI组件
from gui import (
    ElevatorMonitorSystem, SignalBridge, 
    ElevatorCard, CallIndicatorPanel, ModernLogViewer
)


class EnhancedSignalBridge(QObject):
    """增强版信号桥接器 - 支持更多数据信号"""
    log_message = pyqtSignal(str, str)  # message, level
    unit_status = pyqtSignal(dict)
    call_status = pyqtSignal(dict)
    stats_update = pyqtSignal(dict)    # 全面统计数据
    performance_metrics = pyqtSignal(dict)  # 性能指标
    elevator_details = pyqtSignal(dict)  # 电梯详细信息


class GUIOnlyController(ElevatorController):
    """
    纯GUI控制器 - 只接收事件用于显示，不发送控制指令
    设置环境变量 ELEVATOR_CLIENT_TYPE=gui 时使用
    增强版：添加更多监控信息和统计数据
    """
    
    def __init__(self, server_url: str = "http://127.0.0.1:8000", debug: bool = False, signals=None):
        super().__init__(server_url, debug)
        self.signals = signals
        
        # 状态管理（仅用于显示）
        self.unit_state = {}
        self.unit_heading = {}
        self.pending_calls = {"up": set(), "down": set()}
        self.total_levels = 0
        
        # 高级统计数据
        self.stats = {
            # 基本统计
            'total_calls': 0,
            'completed_trips': 0,
            'active_calls': 0,
            'total_wait_time': 0,
            'wait_count': 0,
            'avg_wait_time': 0,
            
            # 增强统计
            'total_travel_time': 0,
            'total_distance_traveled': 0,
            'total_passengers_served': 0,
            'total_floor_stops': 0,
            'total_passenger_distance': 0,
            
            # 性能指标
            'peak_wait_time': 0,
            'peak_passengers': 0,
            'avg_travel_time': 0,
            'service_completion_rate': 0,
            
            # 系统状态
            'simulation_time': 0,
            'active_elevators': 0,
            'idle_elevators': 0,
            'system_uptime': 0,
            
            # 实时指标
            'current_throughput': 0,  # 最近一分钟内服务的乘客数
            'wait_times_last_minute': [],
        }
        
        # 增强的电梯状态跟踪
        self.elevator_details = {}
        self.floor_stats = {}
        self.call_history = []
        self.system_start_time = time.time()
        self.last_stats_update_time = time.time()
        
        # 交通流量分析
        self.traffic_analysis = {
            'calls_by_floor': {},
            'calls_by_direction': {'up': 0, 'down': 0},
            'peak_hours': [],
            'busiest_floors': [],
        }
        
        self._emit_log("GUI模式启动 - 增强版监控系统", "success")

    def on_init(self, elevators: List[ProxyElevator], floors: List[ProxyFloor]) -> None:
        """初始化 - 记录详细信息并初始化统计数据"""
        self.total_levels = len(floors) - 1
        
        # 初始化楼层统计
        for floor in floors:
            self.floor_stats[floor.floor] = {
                'calls': 0,
                'up_calls': 0,
                'down_calls': 0,
                'passengers_served': 0,
                'avg_wait_time': 0,
                'wait_times': []
            }
            self.traffic_analysis['calls_by_floor'][floor.floor] = 0
        
        self._emit_log(f"系统连接 | {len(elevators)}台电梯 | {len(floors)}层楼", "success")
        
        for idx, unit in enumerate(elevators):
            self.unit_state[unit.id] = "idle"
            self.unit_heading[unit.id] = "none"
            
            # 初始化电梯详细信息
            self.elevator_details[unit.id] = {
                'id': unit.id,
                'name': f"电梯{idx + 1}",
                'total_distance': 0,
                'total_stops': 0,
                'passengers_served': 0,
                'total_wait_time': 0,
                'last_floor': unit.current_floor,
                'trip_count': 0,
                'energy_consumption': 0,
                'status_history': []
            }
            
            self._emit_log(f"电梯{idx + 1} 已连接 | 初始位置: F{unit.current_floor}", "info")
            self._emit_unit_status(unit)
        
        # 发送初始统计信息
        self._update_system_stats(elevators)
        self._emit_stats()

    def on_passenger_call(self, passenger: ProxyPassenger, floor: ProxyFloor, direction: str) -> None:
        """呼叫事件 - 显示并更新交通统计"""
        self.pending_calls[direction].add(floor.floor)
        self.stats['total_calls'] += 1
        self.stats['active_calls'] += 1
        
        # 更新楼层统计
        if floor.floor in self.floor_stats:
            self.floor_stats[floor.floor]['calls'] += 1
            self.floor_stats[floor.floor][f'{direction}_calls'] += 1
            self.traffic_analysis['calls_by_floor'][floor.floor] += 1
        
        # 更新方向统计
        self.traffic_analysis['calls_by_direction'][direction] += 1
        
        # 记录呼叫历史
        call_record = {
            'timestamp': time.time(),
            'floor': floor.floor,
            'direction': direction,
            'passenger_id': passenger.id if hasattr(passenger, 'id') else None,
            'status': 'pending'
        }
        self.call_history.append(call_record)
        
        # 如果乘客有目的地，记录预期行程
        if hasattr(passenger, 'destination'):
            self._emit_log(f"新呼叫 @ F{floor.floor} → {direction} → 目标: F{passenger.destination}", "warning")
        else:
            self._emit_log(f"新呼叫 @ F{floor.floor} → {direction}", "warning")
            
        self._emit_call_status()
        self._emit_stats()
        # 不调用任何 go_to_floor 或电梯控制指令

    def on_elevator_move(self, elevator: ProxyElevator, from_pos: float, to_pos: float, 
                        direction: str, status: str) -> None:
        """电梯移动 - 更新显示并计算距离"""
        self.unit_heading[elevator.id] = direction if direction else "none"
        self.unit_state[elevator.id] = status if status else "moving"
        
        # 计算移动距离
        distance = abs(to_pos - from_pos)
        
        # 更新电梯详细信息
        if elevator.id in self.elevator_details:
            self.elevator_details[elevator.id]['total_distance'] += distance
            self.stats['total_distance_traveled'] += distance
            self.elevator_details[elevator.id]['last_floor'] = to_pos
            
            # 记录状态变化
            status_record = {
                'timestamp': time.time(),
                'floor': to_pos,
                'status': status,
                'direction': direction
            }
            self.elevator_details[elevator.id]['status_history'].append(status_record)
        
        # 估算能耗（基于距离和负载）
        load_factor = len(elevator.passengers) / getattr(elevator, 'capacity', 8) if hasattr(elevator, 'passengers') else 0
        energy_consumed = distance * (1 + load_factor * 0.5)  # 负载影响能耗
        if elevator.id in self.elevator_details:
            self.elevator_details[elevator.id]['energy_consumption'] += energy_consumed
        
        self._emit_unit_status(elevator)
        self._emit_stats()

    def on_elevator_stopped(self, elevator: ProxyElevator, floor: ProxyFloor) -> None:
        """电梯停止 - 更新显示并记录停止统计"""
        heading = self.unit_heading[elevator.id]
        
        # 更新呼叫状态
        if heading in self.pending_calls:
            self.pending_calls[heading].discard(floor.floor)
            self.stats['active_calls'] = max(0, self.stats['active_calls'] - 1)
            self._emit_call_status()
        
        # 更新停止统计
        if elevator.id in self.elevator_details:
            self.elevator_details[elevator.id]['total_stops'] += 1
            self.stats['total_floor_stops'] += 1
        
        self.unit_state[elevator.id] = "loading"
        self._emit_log(f"电梯{elevator.id + 1} 停靠 @ F{floor.floor} | 乘客数: {len(elevator.passengers) if hasattr(elevator, 'passengers') else 0}", "success")
        self._emit_unit_status(elevator)
        self._emit_stats()

    def on_passenger_board(self, elevator: ProxyElevator, passenger: ProxyPassenger) -> None:
        """乘客登梯 - 更新详细统计和性能指标"""
        self.stats['completed_trips'] += 1
        self.stats['total_passengers_served'] += 1
        
        # 更新当前吞吐量
        current_time = time.time()
        self.stats['wait_times_last_minute'] = [wt for wt in self.stats['wait_times_last_minute'] if current_time - wt < 60]
        
        # 计算等待时间（如果有时间戳信息）
        if hasattr(passenger, 'call_time') and hasattr(passenger, 'board_time'):
            wait_time = passenger.board_time - passenger.call_time
            self.stats['total_wait_time'] += wait_time
            self.stats['wait_count'] += 1
            self.stats['avg_wait_time'] = self.stats['total_wait_time'] / self.stats['wait_count']
            self.stats['peak_wait_time'] = max(self.stats['peak_wait_time'], wait_time)
            self.stats['wait_times_last_minute'].append(current_time)
            
            # 更新楼层等待时间统计
            if hasattr(passenger, 'origin_floor') and passenger.origin_floor in self.floor_stats:
                self.floor_stats[passenger.origin_floor]['wait_times'].append(wait_time)
                self.floor_stats[passenger.origin_floor]['avg_wait_time'] = sum(self.floor_stats[passenger.origin_floor]['wait_times']) / len(self.floor_stats[passenger.origin_floor]['wait_times'])
        
        # 更新电梯统计
        if elevator.id in self.elevator_details:
            self.elevator_details[elevator.id]['passengers_served'] += 1
            self.elevator_details[elevator.id]['trip_count'] += 1
        
        # 更新呼叫历史
        for call in reversed(self.call_history):
            if (hasattr(passenger, 'origin_floor') and 
                call['floor'] == passenger.origin_floor and 
                call['status'] == 'pending'):
                call['status'] = 'picked_up'
                call['elevator_id'] = elevator.id
                call['pickup_time'] = time.time()
                break
        
        # 更新峰值乘客数
        current_passengers = len(elevator.passengers) if hasattr(elevator, 'passengers') else 0
        self.stats['peak_passengers'] = max(self.stats['peak_passengers'], current_passengers)
        
        # 记录详细的乘客登梯信息
        if hasattr(passenger, 'destination') and hasattr(passenger, 'origin_floor'):
            trip_distance = abs(passenger.destination - passenger.origin_floor)
            self.stats['total_passenger_distance'] += trip_distance
            self._emit_log(f"乘客登梯{elevator.id + 1} | 从 F{passenger.origin_floor} → F{passenger.destination} | 行程距离: {trip_distance}层", "info")
        else:
            self._emit_log(f"乘客登梯{elevator.id + 1} → F{passenger.destination}", "info")
        
        self._emit_unit_status(elevator)
        self._emit_stats()

    def on_passenger_alight(self, elevator: ProxyElevator, passenger: ProxyPassenger, floor: ProxyFloor) -> None:
        """乘客离梯 - 更新完成统计"""
        # 更新楼层统计
        if floor.floor in self.floor_stats:
            self.floor_stats[floor.floor]['passengers_served'] += 1
        
        # 更新交通分析
        self._update_traffic_analysis()
        
        # 更新呼叫历史中对应行程的状态
        for call in reversed(self.call_history):
            if call.get('status') == 'picked_up' and call.get('elevator_id') == elevator.id:
                call['status'] = 'completed'
                call['dropoff_time'] = time.time()
                call['dropoff_floor'] = floor.floor
                break
        
        # 计算并更新总行程时间
        if hasattr(passenger, 'call_time'):
            travel_time = time.time() - passenger.call_time
            self.stats['total_travel_time'] += travel_time
            if self.stats['total_passengers_served'] > 0:
                self.stats['avg_travel_time'] = self.stats['total_travel_time'] / self.stats['total_passengers_served']
        
        # 记录详细的乘客离梯信息
        self._emit_log(f"乘客离梯{elevator.id + 1} @ F{floor.floor}", "info")
        
        self._emit_unit_status(elevator)
        self._emit_stats()

    def on_elevator_idle(self, elevator: ProxyElevator) -> None:
        """电梯空闲 - 记录空闲状态和位置"""
        self.unit_state[elevator.id] = "idle"
        self.unit_heading[elevator.id] = "none"
        
        # 更新电梯状态历史
        if elevator.id in self.elevator_details:
            status_record = {
                'timestamp': time.time(),
                'floor': elevator.current_floor,
                'status': 'idle',
                'direction': 'none'
            }
            self.elevator_details[elevator.id]['status_history'].append(status_record)
        
        self._emit_log(f"电梯{elevator.id + 1} 空闲 @ F{elevator.current_floor}", "info")
        self._emit_unit_status(elevator)
        self._emit_stats()

    def on_elevator_passing_floor(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        """经过楼层 - 记录经过信息"""
        self._emit_log(f"电梯{elevator.id + 1} 经过 F{floor.floor} → {direction}", "debug")

    def on_elevator_approaching(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        """接近楼层 - 提前通知"""
        self._emit_log(f"电梯{elevator.id + 1} 接近 F{floor.floor} → {direction}", "info")

    def on_event_execute_start(self, tick, events, elevators, floors):
        """事件执行开始 - 更新系统时间"""
        # 更新模拟时间和系统统计
        self.stats['simulation_time'] = tick
        self._update_system_stats(elevators)

    def on_event_execute_end(self, tick, events, elevators, floors):
        """事件执行结束 - 更新实时统计"""
        # 定期更新统计信息
        current_time = time.time()
        if current_time - self.last_stats_update_time > 5:  # 每5秒更新一次
            self._update_realtime_metrics()
            self.last_stats_update_time = current_time

    def _emit_log(self, message, level='info'):
        """发送日志"""
        if self.signals:
            self.signals.log_message.emit(message, level)

    def _emit_unit_status(self, unit):
        """发送电梯详细状态"""
        if self.signals:
            # 收集目标楼层（从乘客目的地）
            targets = []
            passenger_details = []
            
            if hasattr(unit, 'passengers'):
                targets = list(set(p.destination for p in unit.passengers if hasattr(p, 'destination')))
                # 收集乘客详细信息
                for p in unit.passengers:
                    passenger_info = {
                        'destination': p.destination if hasattr(p, 'destination') else 'unknown',
                        'id': p.id if hasattr(p, 'id') else None
                    }
                    if hasattr(p, 'origin_floor'):
                        passenger_info['origin'] = p.origin_floor
                    passenger_details.append(passenger_info)
            
            # 获取电梯详细统计
            elevator_stats = self.elevator_details.get(unit.id, {})
            
            # 构建完整的电梯状态数据
            data = {
                'id': unit.id,
                'current_level': unit.current_floor,
                'heading': self.unit_heading[unit.id],
                'status': self.unit_state[unit.id],
                'load_count': len(unit.passengers) if hasattr(unit, 'passengers') else 0,
                'targets': targets,
                
                # 增强信息
                'passenger_details': passenger_details,
                'total_distance': elevator_stats.get('total_distance', 0),
                'total_stops': elevator_stats.get('total_stops', 0),
                'passengers_served': elevator_stats.get('passengers_served', 0),
                'energy_consumption': elevator_stats.get('energy_consumption', 0),
                
                # 实时状态
                'moving': getattr(unit, 'moving', False),
                'doors_open': getattr(unit, 'doors_open', False),
                'capacity': getattr(unit, 'capacity', 8),
                'load_percentage': (len(unit.passengers) / getattr(unit, 'capacity', 8) * 100) if hasattr(unit, 'passengers') else 0,
                
                # 性能指标
                'avg_wait_time': elevator_stats.get('total_wait_time', 0) / max(1, elevator_stats.get('passengers_served', 1))
            }
            
            self.signals.unit_status.emit(data)
            
            # 如果有自定义信号用于发送详细统计，也发送
            if hasattr(self.signals, 'elevator_details'):
                self.signals.elevator_details.emit(data)

    def _emit_call_status(self):
        """发送增强的呼叫状态"""
        if self.signals:
            # 分析呼叫分布
            total_calls = len(self.pending_calls["up"]) + len(self.pending_calls["down"])
            
            # 找出高需求楼层
            high_demand_floors = []
            for floor in range(self.total_levels + 1):
                if (floor in self.pending_calls["up"] or floor in self.pending_calls["down"]) and \
                   self.floor_stats.get(floor, {}).get('calls', 0) > 5:
                    high_demand_floors.append(floor)
            
            data = {
                'up_calls': self.pending_calls["up"],
                'down_calls': self.pending_calls["down"],
                'total_pending': total_calls,
                'high_demand_floors': high_demand_floors,
                'call_density': {
                    'up': len(self.pending_calls["up"]),
                    'down': len(self.pending_calls["down"])
                }
            }
            
            self.signals.call_status.emit(data)

    def _emit_stats(self):
        """发送全面的统计数据和分析"""
        if self.signals and hasattr(self.signals, 'stats_update'):
            # 更新完成率
            if self.stats['total_calls'] > 0:
                self.stats['service_completion_rate'] = (self.stats['completed_trips'] / self.stats['total_calls']) * 100
            
            # 准备完整的统计数据包
            stats_package = {
                **self.stats,
                'floor_stats': self.floor_stats,
                'traffic_analysis': self.traffic_analysis,
                'elevator_performance': {}
            }
            
            # 添加每台电梯的性能数据
            for elevator_id, details in self.elevator_details.items():
                stats_package['elevator_performance'][elevator_id] = {
                    'total_distance': details.get('total_distance', 0),
                    'passengers_served': details.get('passengers_served', 0),
                    'total_stops': details.get('total_stops', 0),
                    'energy_consumption': details.get('energy_consumption', 0),
                    'efficiency': details.get('passengers_served', 0) / max(1, details.get('total_distance', 1))
                }
            
            # 计算系统效率指标
            total_elevators = len(self.elevator_details)
            if total_elevators > 0:
                stats_package['avg_elevator_efficiency'] = (
                    sum(e['efficiency'] for e in stats_package['elevator_performance'].values()) / total_elevators
                )
            
            self.signals.stats_update.emit(stats_package)
            
            # 如果有单独的性能信号，也发送性能数据
            if hasattr(self.signals, 'performance_metrics'):
                performance_data = {
                    'throughput': self.stats['current_throughput'],
                    'avg_response_time': self.stats['avg_wait_time'],
                    'service_completion_rate': self.stats['service_completion_rate'],
                    'system_efficiency': stats_package.get('avg_elevator_efficiency', 0)
                }
                self.signals.performance_metrics.emit(performance_data)
    
    def _update_system_stats(self, elevators: List[ProxyElevator]):
        """更新系统级统计数据"""
        # 计算活跃和空闲电梯数量
        idle_count = 0
        active_count = 0
        
        for elevator in elevators:
            if elevator.id in self.unit_state:
                if self.unit_state[elevator.id] == 'idle':
                    idle_count += 1
                else:
                    active_count += 1
        
        self.stats['active_elevators'] = active_count
        self.stats['idle_elevators'] = idle_count
        self.stats['system_uptime'] = time.time() - self.system_start_time
    
    def _update_realtime_metrics(self):
        """更新实时性能指标"""
        # 计算最近一分钟的吞吐量
        current_time = time.time()
        recent_pickups = len([t for t in self.stats['wait_times_last_minute'] if current_time - t < 60])
        self.stats['current_throughput'] = recent_pickups
    
    def _update_traffic_analysis(self):
        """更新交通流量分析"""
        # 更新最繁忙楼层
        calls_by_floor = sorted(
            [(floor, data) for floor, data in self.floor_stats.items()],
            key=lambda x: x[1]['calls'],
            reverse=True
        )
        
        self.traffic_analysis['busiest_floors'] = calls_by_floor[:5]  # 前5个最繁忙楼层
        
        # 更新高峰时段（简化版本，基于当前时间）
        current_hour = datetime.now().hour
        self.traffic_analysis['peak_hours'].append({
            'hour': current_hour,
            'calls': self.stats['total_calls'],
            'timestamp': time.time()
        })


class GUIMonitorSystem(ElevatorMonitorSystem):
    """
    GUI监控系统 - 适配纯显示模式
    """
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("智能电梯监控系统 - GUI模式")
        # 替换为增强版信号桥接器
        self.signals = EnhancedSignalBridge()
        
    def start_simulation(self):
        """启动模拟 - 使用GUI专用控制器（作为观察者模式，不执行重置）"""
        self.log_viewer.append_log("GUI模式启动 - 连接到运行中的模拟器...", "success")
        self.start_btn.setEnabled(False)
        
        # 创建GUI专用控制器
        self.controller = GUIOnlyController(
            server_url="http://127.0.0.1:8000",
            debug=True,
            signals=self.signals
        )
        
        # 创建默认电梯卡片（会根据实际连接数量调整）
        self.create_unit_cards(4)
        
        # 启动模拟线程，但修改run_simulation方法避免重置
        import threading
        self.sim_thread = threading.Thread(target=self.run_simulation_observable)
        self.sim_thread.daemon = True
        self.sim_thread.start()
    
    def run_simulation_observable(self):
        """作为观察者运行模拟，不执行重置操作，并确保GUI更新"""
        print("开始运行观察者模式...")
        try:
            # 直接初始化而不重置
            print("初始化控制器...")
            self.controller.on_start()
            
            # 使用自定义的运行循环，只监听状态变化
            self.controller.is_running = True
            print("控制器已启动，开始监听状态变化...")
            
            # 记录上一次的状态，用于检测变化
            last_elevator_states = {}
            tick_count = 0
            last_algorithm_tick = -1
            discovered_elevators = set()  # 跟踪已发现的电梯ID
            force_refresh_interval = 3  # 缩短强制刷新间隔
            
            while self.controller.is_running:
                try:
                    tick_count += 1
                    if tick_count % 10 == 0:
                        print(f"已运行 {tick_count} 个检查周期，上次算法tick: {last_algorithm_tick}，已发现电梯: {discovered_elevators}")
                    
                    # 获取最新状态 - 使用force_reload=True确保获取最新数据
                    print(f"周期 {tick_count}: 获取状态...")
                    
                    # 检查并记录当前所有可用的电梯
                    state = self.controller.api_client.get_state(force_reload=True)
                    print(f"周期 {tick_count}: 成功获取状态，当前tick: {state.tick}，总电梯数: {len(state.elevators)}")
                    
                    # 记录所有发现的电梯
                    current_elevator_ids = set(e.id for e in state.elevators)
                    new_elevators = current_elevator_ids - discovered_elevators
                    if new_elevators:
                        print(f"  新发现电梯: {new_elevators}")
                        discovered_elevators.update(new_elevators)
                        print(f"  当前所有电梯: {discovered_elevators}")
                    
                    # 处理tick值异常跳变的情况
                    if hasattr(state, 'tick'):
                        # 检查tick值是否有异常跳变（可能是算法重启）
                        if state.tick < last_algorithm_tick and last_algorithm_tick > 0:
                            print(f"  警告: 检测到算法tick异常跳变: {last_algorithm_tick} → {state.tick}，可能是算法重启")
                            # 重置电梯状态记录，以便重新初始化
                            last_elevator_states.clear()
                        
                        last_algorithm_tick = state.tick
                        print(f"  更新算法tick: {last_algorithm_tick}")
                    
                    # 无论是否初始化过，都更新和处理所有电梯
                    print(f"周期 {tick_count}: 更新电梯状态")
                    
                    # 打印每个电梯的详细信息
                    for elevator in state.elevators:
                        # 获取所有可能的电梯属性，添加更详细的日志
                        elevator_id = elevator.id
                        current_floor = elevator.current_floor
                        direction = getattr(elevator, 'direction', 'none')
                        elevator_passengers = len(elevator.passengers) if hasattr(elevator, 'passengers') else 0
                        elevator_status = getattr(elevator, 'status', 'unknown')
                        
                        # 尝试获取更多可能的电梯属性
                        moving = getattr(elevator, 'moving', False)
                        doors_open = getattr(elevator, 'doors_open', False)
                        
                        print(f"  电梯 {elevator_id} 详情: 楼层={current_floor}, 方向={direction}, 乘客={elevator_passengers}, "
                              f"状态={elevator_status}, 移动中={moving}, 门开={doors_open}")
                        
                        # 构建更完整的电梯状态数据
                        elevator_data = {
                            'current_floor': current_floor,
                            'passengers': elevator_passengers,
                            'status': elevator_status,
                            'direction': direction,
                            'moving': moving,
                            'doors_open': doors_open,
                            # 使用本地tick作为额外的变化检测因素
                            'local_timestamp': tick_count,
                            # 添加算法tick作为同步参考
                            'algorithm_tick': state.tick if hasattr(state, 'tick') else -1
                        }
                        
                        # 检查电梯状态是否有变化或需要强制更新
                        elevator_changed = False
                        
                        # 如果是新电梯，标记为变化
                        if elevator_id not in last_elevator_states:
                            elevator_changed = True
                            print(f"  发现新电梯 {elevator_id}，将初始化其状态")
                        else:
                            # 更宽松的变化检测逻辑
                            old_data = last_elevator_states[elevator_id]
                            # 任何关键属性变化都触发更新
                            if (old_data['current_floor'] != elevator_data['current_floor'] or 
                                old_data['direction'] != elevator_data['direction'] or
                                old_data['passengers'] != elevator_data['passengers'] or
                                old_data['moving'] != elevator_data['moving'] or
                                old_data['doors_open'] != elevator_data['doors_open']):
                                elevator_changed = True
                                print(f"  电梯 {elevator_id} 状态变化: 楼层={old_data['current_floor']}→{elevator_data['current_floor']}, "
                                      f"方向={old_data['direction']}→{elevator_data['direction']}, "
                                      f"移动={old_data['moving']}→{elevator_data['moving']}")
                        
                        # 更频繁地强制更新所有电梯
                        if not elevator_changed and tick_count % force_refresh_interval == 0:
                            elevator_changed = True
                            print(f"  电梯 {elevator_id} 强制更新 (每{force_refresh_interval}个周期)")
                        
                        # 如果状态有变化，更新并发送信号
                        if elevator_changed:
                            last_elevator_states[elevator_id] = elevator_data.copy()
                            
                            # 直接发送状态更新信号
                            if self.signals:
                                print(f"  发送电梯 {elevator_id} 的状态更新")
                                
                                # 收集目标楼层（从乘客目的地）
                                targets = []
                                if hasattr(elevator, 'passengers'):
                                    targets = list(set(p.destination for p in elevator.passengers if hasattr(p, 'destination')))
                                
                                # 构建完整的单元状态数据
                                unit_status_data = {
                                    'id': elevator_id,
                                    'current_level': current_floor,
                                    'heading': direction,
                                    'status': elevator_status,
                                    'load_count': elevator_passengers,
                                    'targets': targets,
                                    # 添加额外字段帮助调试
                                    'moving': moving,
                                    'doors_open': doors_open,
                                    'tick': state.tick if hasattr(state, 'tick') else -1
                                }
                                print(f"  发送的数据: {unit_status_data}")
                                self.signals.unit_status.emit(unit_status_data)
                    
                    # 处理可能丢失的电梯（已发现但当前未返回）
                    missing_elevators = discovered_elevators - current_elevator_ids
                    if missing_elevators:
                        print(f"  警告: 未在当前状态中找到电梯: {missing_elevators}")
                        # 对于丢失的电梯，也定期尝试重新发送其最后状态
                        if tick_count % (force_refresh_interval * 2) == 0:
                            for elevator_id in missing_elevators:
                                if elevator_id in last_elevator_states:
                                    print(f"  重新发送丢失电梯 {elevator_id} 的最后已知状态")
                                    if self.signals:
                                        last_data = last_elevator_states[elevator_id]
                                        unit_status_data = {
                                            'id': elevator_id,
                                            'current_level': last_data['current_floor'],
                                            'heading': last_data['direction'],
                                            'status': last_data['status'],
                                            'load_count': last_data['passengers'],
                                            'targets': [],
                                            'moving': last_data['moving'],
                                            'doors_open': last_data['doors_open'],
                                            'tick': -1
                                        }
                                        self.signals.unit_status.emit(unit_status_data)
                    
                    # 模拟tick事件
                    self.controller.current_tick = state.tick if hasattr(state, 'tick') else tick_count
                    
                    # 适当调整休眠时间
                    import time
                    time.sleep(0.2)
                    
                except Exception as e:
                    error_msg = f"状态更新错误: {str(e)}"
                    print(error_msg)
                    if hasattr(self, 'log_viewer'):
                        self.log_viewer.append_log(error_msg, "error")
                    import traceback
                    traceback.print_exc()
                    import time
                    time.sleep(1)
                    
        except Exception as e:
            error_msg = f"模拟运行错误: {str(e)}"
            print(error_msg)
            if hasattr(self, 'log_viewer'):
                self.log_viewer.append_log(error_msg, "error")
            import traceback
            traceback.print_exc()
        finally:
            print("停止观察者模式运行")
            self.controller.on_stop()


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
