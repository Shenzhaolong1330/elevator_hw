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
