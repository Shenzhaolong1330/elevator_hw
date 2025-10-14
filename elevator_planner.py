#!/usr/bin/env python3
from typing import List, Dict, Set, Optional

from elevator_saga.client.base_controller import ElevatorController
from elevator_saga.client.proxy_models import ProxyElevator, ProxyFloor, ProxyPassenger
from elevator_saga.core.models import SimulationEvent, Direction


class ElevatorPlanner(ElevatorController):
    """
    基于LOOK算法的电梯调度系统
    电梯会在一个方向上移动，直到该方向上没有更多请求，然后改变方向
    优化目标：最小化所有乘客的等待时间总和和95%乘客的等待时间总和
    """
    
    def __init__(self, server_url: str = "http://127.0.0.1:8000", debug: bool = False):
        super().__init__(server_url, debug)
        self.elevator_directions: Dict[int, str] = {}  # 记录每个电梯的当前方向
        self.elevator_up_requests: Dict[int, Set[int]] = {}  # 每个电梯的上行请求
        self.elevator_down_requests: Dict[int, Set[int]] = {}  # 每个电梯的下行请求
        self.max_floor: int = 0  # 最大楼层数
        self.floors: List[ProxyFloor] = []  # 所有楼层
        self.elevators: List[ProxyElevator] = []  # 所有电梯

    def on_init(self, elevators: List[ProxyElevator], floors: List[ProxyFloor]) -> None:
        """初始化电梯调度算法"""
        print("🚀 基于LOOK算法的电梯调度系统初始化")
        print(f"   管理 {len(elevators)} 部电梯")
        print(f"   服务 {len(floors)} 层楼")
        
        # 初始化属性
        self.elevators = elevators
        self.floors = floors
        self.max_floor = len(floors) - 1
        
        # 初始化每个电梯的数据结构
        for elevator in elevators:
            self.elevator_directions[elevator.id] = "up"  # 初始方向向上
            self.elevator_up_requests[elevator.id] = set()  # 上行请求集合
            self.elevator_down_requests[elevator.id] = set()  # 下行请求集合
        
        # 简单的初始分布 - 均匀分散到不同楼层
        for i, elevator in enumerate(elevators):
            # 计算目标楼层 - 均匀分布在不同楼层
            target_floor = (i * (len(floors) - 1)) // len(elevators)
            # 立刻移动到目标位置
            elevator.go_to_floor(target_floor, immediate=True)

    def on_event_execute_start(
        self, tick: int, events: List[SimulationEvent], elevators: List[ProxyElevator], floors: List[ProxyFloor]
    ) -> None:
        """事件执行前的回调"""
        if self.debug:
            print(f"Tick {tick}: 即将处理 {len(events)} 个事件 {[e.type.value for e in events]}")
            for elevator in elevators:
                print(
                    f"\t电梯 {elevator.id}[{elevator.target_floor_direction.value},{elevator.current_floor_float}/{elevator.target_floor}]" +
                    "👦" * len(elevator.passengers),
                    end="",
                )
            print()

    def on_event_execute_end(
        self, tick: int, events: List[SimulationEvent], elevators: List[ProxyElevator], floors: List[ProxyFloor]
    ) -> None:
        """事件执行后的回调"""
        # 更新电梯状态并确保电梯持续运行
        for elevator in elevators:
            self._ensure_elevator_has_target(elevator)

    def on_passenger_call(self, passenger: ProxyPassenger, floor: ProxyFloor, direction: str) -> None:
        """乘客呼叫时的回调"""
        if self.debug:
            print(f"👤 乘客 {passenger.id} 在 F{floor.floor} 请求 {passenger.origin} -> {passenger.destination} ({direction})")
        
        # 为乘客分配最合适的电梯
        best_elevator = self._find_best_elevator_for_passenger(passenger, floor, direction)
        if best_elevator:
            # 将请求添加到电梯的请求集合
            if direction == "up":
                self.elevator_up_requests[best_elevator.id].add(floor.floor)
            else:
                self.elevator_down_requests[best_elevator.id].add(floor.floor)
            
            # 更新电梯的目标
            self._update_elevator_target(best_elevator)

    def on_elevator_idle(self, elevator: ProxyElevator) -> None:
        """电梯空闲时的回调"""
        if self.debug:
            print(f"🛑 电梯 E{elevator.id} 在 F{elevator.current_floor} 层空闲")
        
        # 确保电梯有目标楼层
        self._ensure_elevator_has_target(elevator)

    def on_elevator_stopped(self, elevator: ProxyElevator, floor: ProxyFloor) -> None:
        """电梯停靠时的回调"""
        if self.debug:
            print(f"🛑 电梯 E{elevator.id} 停靠在 F{floor.floor}")
        
        # 移除当前楼层的请求
        if floor.floor in self.elevator_up_requests[elevator.id]:
            self.elevator_up_requests[elevator.id].remove(floor.floor)
        if floor.floor in self.elevator_down_requests[elevator.id]:
            self.elevator_down_requests[elevator.id].remove(floor.floor)
        
        # 更新电梯目标
        self._update_elevator_target(elevator)

    def on_passenger_board(self, elevator: ProxyElevator, passenger: ProxyPassenger) -> None:
        """乘客进入电梯时的回调"""
        if self.debug:
            print(f"✅ 乘客 {passenger.id} 进入电梯 E{elevator.id}")
        
        # 不需要特别处理，因为电梯内部的目标楼层由系统自动处理

    def on_passenger_alight(self, elevator: ProxyElevator, passenger: ProxyPassenger, floor: ProxyFloor) -> None:
        """乘客离开电梯时的回调"""
        if self.debug:
            print(f"✅ 乘客 {passenger.id} 离开电梯 E{elevator.id}，到达 F{floor.floor}")

    def on_elevator_passing_floor(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        """电梯经过楼层时的回调"""
        pass  # 不做特别处理

    def on_elevator_approaching(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        """电梯接近楼层时的回调"""
        pass  # 不做特别处理
        
    def _find_best_elevator_for_passenger(self, passenger: ProxyPassenger, floor: ProxyFloor, direction: str) -> Optional[ProxyElevator]:
        """
        为乘客找到最合适的电梯
        考虑因素：电梯当前位置、运行方向、载客量、已有请求数量
        """
        best_elevator = None
        best_score = float('inf')
        
        for elevator in self.elevators:
            # 如果电梯已满，跳过
            if elevator.is_full:
                continue
            
            # 计算电梯到乘客所在楼层的距离
            distance = abs(elevator.current_floor - floor.floor)
            
            # 计算得分，距离越近、载客量越少得分越低（越好）
            # 优先考虑同方向的电梯
            direction_factor = 1.0
            if elevator.target_floor_direction.value == direction or elevator.is_idle:
                direction_factor = 0.5
            
            # 当前电梯的请求数量
            request_count = len(self.elevator_up_requests[elevator.id]) + len(self.elevator_down_requests[elevator.id])
            
            # 综合得分
            score = distance * direction_factor + elevator.load_factor * 10 + request_count * 0.5
            
            # 更新最佳电梯
            if score < best_score:
                best_score = score
                best_elevator = elevator
        
        return best_elevator
    
    def _update_elevator_target(self, elevator: ProxyElevator) -> None:
        """根据当前请求更新电梯的目标楼层"""
        current_floor = elevator.current_floor
        direction = self.elevator_directions[elevator.id]
        
        # 收集所有请求楼层和电梯内部乘客的目标楼层
        target_floors = set()
        
        # 添加电梯内部乘客的目标楼层
        if hasattr(elevator, 'pressed_floors'):
            target_floors.update(elevator.pressed_floors)
        
        # 添加外部请求楼层
        if direction == "up":
            target_floors.update(self.elevator_up_requests[elevator.id])
        else:
            target_floors.update(self.elevator_down_requests[elevator.id])
        
        # 如果没有目标楼层，检查另一个方向
        if not target_floors:
            if direction == "up":
                target_floors.update(self.elevator_down_requests[elevator.id])
                if target_floors:
                    direction = "down"
            else:
                target_floors.update(self.elevator_up_requests[elevator.id])
                if target_floors:
                    direction = "up"
        
        # 更新电梯方向
        self.elevator_directions[elevator.id] = direction
        
        # 根据当前方向和楼层选择下一个目标楼层
        if target_floors:
            if direction == "up":
                # 在当前楼层之上的最近目标楼层
                above_targets = [f for f in target_floors if f > current_floor]
                if above_targets:
                    next_floor = min(above_targets)
                else:
                    # 如果当前方向没有更高的目标，改变方向
                    next_floor = max(target_floors)
                    self.elevator_directions[elevator.id] = "down"
            else:
                # 在当前楼层之下的最近目标楼层
                below_targets = [f for f in target_floors if f < current_floor]
                if below_targets:
                    next_floor = max(below_targets)
                else:
                    # 如果当前方向没有更低的目标，改变方向
                    next_floor = min(target_floors)
                    self.elevator_directions[elevator.id] = "up"
            
            # 设置电梯目标
            elevator.go_to_floor(next_floor)
    
    def _ensure_elevator_has_target(self, elevator: ProxyElevator) -> None:
        """确保电梯始终有目标楼层"""
        # 如果电梯没有目标或者已经到达目标，更新目标
        if elevator.is_idle:
            self._update_elevator_target(elevator)


if __name__ == "__main__":
    # 创建电梯调度器实例并启动
    planner = ElevatorPlanner(debug=True)
    planner.start()
