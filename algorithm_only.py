#!/usr/bin/env python3
"""
智能电梯调度算法 - 纯算法模式
只负责控制逻辑，不提供GUI
"""
import os
from typing import List, Dict, Set
from collections import defaultdict

from elevator_saga.client.base_controller import ElevatorController
from elevator_saga.client.proxy_models import ProxyElevator, ProxyFloor, ProxyPassenger
from elevator_saga.core.models import Direction


class IntelligentDispatchController(ElevatorController):
    """
    智能调度算法控制器
    设置环境变量 ELEVATOR_CLIENT_TYPE=algorithm 时使用
    """
    
    def __init__(self, server_url: str = "http://127.0.0.1:8000", debug: bool = False):
        super().__init__(server_url, debug)
        
        # 状态管理
        self.unit_state: Dict[int, str] = {}
        self.unit_heading: Dict[int, str] = {}
        self.service_queue: Dict[int, List[int]] = {}
        self.passenger_registry: Dict[int, Dict[int, int]] = {}
        self.pending_calls = {"up": set(), "down": set()}
        
        self.total_levels = 0
        self.unit_capacity = 10
        self.zone_assignment: Dict[int, tuple] = {}
        
        # 统计数据
        self.total_energy = 0  # 总能耗
        self.move_count = {i: 0 for i in range(10)}  # 每台电梯移动次数
        
        if debug:
            print("[算法] 智能调度算法已启动")

    def on_init(self, elevators: List[ProxyElevator], floors: List[ProxyFloor]) -> None:
        """初始化"""
        self.total_levels = len(floors) - 1
        
        if self.debug:
            print(f"[算法] 系统初始化 | {len(elevators)}台电梯 | {len(floors)}层楼")
        
        for idx, unit in enumerate(elevators):
            self.unit_state[unit.id] = "idle"
            self.unit_heading[unit.id] = "none"
            self.service_queue[unit.id] = []
            self.passenger_registry[unit.id] = {}
            
            # 计算初始位置和服务区域
            home_level = self._calculate_home_position(idx, len(elevators))
            self.zone_assignment[unit.id] = self._get_service_zone(idx, len(elevators))
            
            # 移动到初始位置
            unit.go_to_floor(home_level, immediate=True)
            
            if self.debug:
                print(f"[算法] 电梯{idx + 1} 初始化 @ F{home_level}, 区域: {self.zone_assignment[unit.id]}")

    def _calculate_home_position(self, index: int, total: int) -> int:
        """计算初始位置 - 均匀分布"""
        if total == 1:
            return self.total_levels // 2
        segment = (self.total_levels + 1) / total
        return min(int(index * segment + segment / 2), self.total_levels)

    def _get_service_zone(self, index: int, total: int) -> tuple:
        """获取服务区域 - 分区策略"""
        if total == 1:
            return (0, self.total_levels)
        zone_size = (self.total_levels + 1) / total
        start = int(index * zone_size)
        end = int((index + 1) * zone_size) if index < total - 1 else self.total_levels
        return (start, end)

    def on_passenger_call(self, passenger: ProxyPassenger, floor: ProxyFloor, direction: str) -> None:
        """处理呼叫 - 智能派梯"""
        self.pending_calls[direction].add(floor.floor)
        
        if self.debug:
            print(f"[算法] 新呼叫 @ F{floor.floor} → {direction}")
        
        # 智能派梯
        self._intelligent_dispatch(floor.floor, direction)

    def _intelligent_dispatch(self, target_floor: int, direction: str):
        """智能派梯算法 - 综合评分"""
        candidates = []
        
        for unit in self.elevators:
            score = self._calculate_score(unit, target_floor, direction)
            if score > 0:
                candidates.append((score, unit.id, unit))
        
        if candidates:
            # 选择评分最高的电梯
            candidates.sort(reverse=True)
            _, best_id, best_unit = candidates[0]
            self._assign_task(best_unit, target_floor)
            
            if self.debug:
                print(f"[算法] 分配电梯{best_id + 1} 响应 F{target_floor} (评分: {candidates[0][0]:.1f})")

    def _calculate_score(self, unit: ProxyElevator, target_floor: int, direction: str) -> float:
        """计算派梯评分"""
        score = 0.0
        state = self.unit_state[unit.id]
        
        # 空闲电梯 - 距离越近分数越高
        if state == "idle":
            distance = abs(unit.current_floor - target_floor)
            score = 100 - distance * 2
            
            # 在服务区域内加分
            zone_start, zone_end = self.zone_assignment[unit.id]
            if zone_start <= target_floor <= zone_end:
                score += 50
        
        # 运行中电梯 - 顺路加分
        elif state == "moving":
            heading = self.unit_heading[unit.id]
            if heading == direction:
                # 同方向且在路径上
                if (heading == "up" and unit.current_floor < target_floor) or \
                   (heading == "down" and unit.current_floor > target_floor):
                    distance = abs(unit.current_floor - target_floor)
                    score = 80 - distance
                    
                    # 负载因子 - 越空越好
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
        """执行下一个任务 - SCAN算法"""
        queue = self.service_queue[unit.id]
        
        if not queue:
            self.unit_state[unit.id] = "idle"
            self.unit_heading[unit.id] = "none"
            return
        
        current = unit.current_floor
        heading = self.unit_heading[unit.id]
        
        # SCAN算法：继续当前方向直到没有目标，然后反向
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
        
        # 发送移动指令
        unit.go_to_floor(next_floor)
        
        if self.debug:
            print(f"[算法] 电梯{unit.id + 1} → F{next_floor} ({self.unit_heading[unit.id]})")

    def on_elevator_move(self, elevator: ProxyElevator, from_pos: float, to_pos: float,
                        direction: str, status: str) -> None:
        """电梯移动 - 记录能耗"""
        # 记录移动次数（用于能耗计算）
        if int(from_pos) != int(to_pos):
            self.move_count[elevator.id] += 1
            
            # 1-3号电梯能耗为1，4号电梯能耗为2
            energy = 2 if elevator.id == 3 else 1
            self.total_energy += energy

    def on_elevator_stopped(self, elevator: ProxyElevator, floor: ProxyFloor) -> None:
        """电梯停靠"""
        # 从队列中移除
        if floor.floor in self.service_queue[elevator.id]:
            self.service_queue[elevator.id].remove(floor.floor)
        
        # 清除对应的呼叫
        heading = self.unit_heading[elevator.id]
        if heading in self.pending_calls:
            self.pending_calls[heading].discard(floor.floor)
        
        self.unit_state[elevator.id] = "loading"
        
        if self.debug:
            print(f"[算法] 电梯{elevator.id + 1} 停靠 @ F{floor.floor}")
        
        # 继续下一个任务
        if self.service_queue[elevator.id] or self.passenger_registry[elevator.id]:
            self._execute_next(elevator)
        else:
            self.unit_state[elevator.id] = "idle"
            self.unit_heading[elevator.id] = "none"

    def on_passenger_board(self, elevator: ProxyElevator, passenger: ProxyPassenger) -> None:
        """乘客登梯"""
        self.passenger_registry[elevator.id][passenger.id] = passenger.destination
        
        # 添加目的地到队列
        if passenger.destination not in self.service_queue[elevator.id]:
            self.service_queue[elevator.id].append(passenger.destination)
        
        if self.debug:
            print(f"[算法] 乘客登梯{elevator.id + 1} → F{passenger.destination}")

    def on_passenger_alight(self, elevator: ProxyElevator, passenger: ProxyPassenger, floor: ProxyFloor) -> None:
        """乘客离梯"""
        if passenger.id in self.passenger_registry[elevator.id]:
            del self.passenger_registry[elevator.id][passenger.id]

    def on_elevator_idle(self, elevator: ProxyElevator) -> None:
        """电梯空闲"""
        self.service_queue[elevator.id].clear()
        self.unit_state[elevator.id] = "idle"
        self.unit_heading[elevator.id] = "none"

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


def main():
    """主函数"""
    # 设置环境变量
    os.environ['ELEVATOR_CLIENT_TYPE'] = 'algorithm'
    
    controller = IntelligentDispatchController(
        server_url="http://127.0.0.1:8000",
        debug=True
    )
    
    print("[算法] 启动算法控制器...")
    controller.start()


if __name__ == '__main__':
    main()
