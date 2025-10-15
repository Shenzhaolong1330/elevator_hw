#!/usr/bin/env python3
from typing import List, Dict, Set, Optional
import requests
import json

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
        self.all_passengers: List[ProxyPassenger] = []  # 所有乘客
        self.backend_url = "http://127.0.0.1:5000"  # 后端服务地址
        self.current_tick = 0  # 当前时间刻度
        self.events_log = []  # 事件日志
        self.passenger_wait_time: Dict[int, int] = {}  # 乘客等待时间记录
        self.last_elevator_target: Dict[int, int] = {}  # 电梯上次目标楼层记录，防止重复命令
        
        # 尝试连接后端
        self.backend_available = self._check_backend()
    
    def _check_backend(self) -> bool:
        """检查后端服务是否可用"""
        try:
            response = requests.get(f"{self.backend_url}/health", timeout=2)
            if response.status_code == 200:
                print("✅ 后端服务连接成功")
                return True
        except Exception as e:
            print(f"⚠️  后端服务不可用: {e}")
            print("   继续运行，可视化功能将被禁用")
        return False
    
    def _send_state_to_backend(self, elevators: List[ProxyElevator]) -> None:
        """将电梯状态发送到后端"""
        if not self.backend_available:
            return
        
        try:
            # 构建电梯数据
            elevator_data = []
            for elevator in elevators:
                elevator_data.append({
                    "id": elevator.id,
                    "current_floor": round(elevator.current_floor_float, 1),
                    "target_floor": elevator.target_floor,
                    "passengers": len(elevator.passengers),
                    "direction": elevator.target_floor_direction.value,
                    "capacity": 8
                })
            
            # 构建事件日志
            events_data = [
                {
                    "type": e.type.value,
                    "description": str(e)
                }
                for e in self.events_log[-10:]  # 只发送最后10个事件
            ]

            # 构建乘客数据
            passengers_data = [
                {
                    "id": p.id,
                    "origin": p.origin,
                    "destination": p.destination
                }
                for p in self.all_passengers[-50:]  # 只发送最后50个乘客
            ]

            payload = {
                "tick": self.current_tick,
                "elevators": elevator_data,
                "events": events_data,
                "passengers": passengers_data,
                "max_floor": self.max_floor
            }

            requests.post(
                f"{self.backend_url}/api/update",
                json=payload,
                timeout=2
            )
        except Exception as e:
            # 静默处理错误，不打断主程序
            pass

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
        self.current_tick = tick
        self.events_log = events
        
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
        # 将电梯状态发送到后端
        self._send_state_to_backend(elevators)
        
        # 更新电梯状态并确保电梯持续运行
        for elevator in elevators:
            self._ensure_elevator_has_target(elevator)

    def on_passenger_call(self, passenger: ProxyPassenger, floor: ProxyFloor, direction: str) -> None:
        """乘客呼叫时的回调"""
        # 记录乘客信息
        self.all_passengers.append(passenger)
        self.passenger_wait_time[passenger.id] = self.current_tick  # 记录乘客开始等待时间
        
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
            # 计算乘客等待时间
            wait_time = self.current_tick - self.passenger_wait_time.get(passenger.id, self.current_tick)
            print(f"✅ 乘客 {passenger.id} 进入电梯 E{elevator.id} (等待时间: {wait_time} 刻度)")
        
        # 清除乘客等待记录
        if passenger.id in self.passenger_wait_time:
            del self.passenger_wait_time[passenger.id]

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
        优化版本：考虑更多因素，包括电梯当前运行方向、乘客目标楼层、电梯负载等
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
            is_same_direction = elevator.target_floor_direction.value == direction
            is_idle = elevator.is_idle
            is_approaching = False
            
            # 检查电梯是否正在接近乘客所在楼层
            if elevator.target_floor_direction.value == "up" and elevator.current_floor < floor.floor:
                is_approaching = True
            elif elevator.target_floor_direction.value == "down" and elevator.current_floor > floor.floor:
                is_approaching = True
            
            # 方向因子优化
            if is_same_direction and is_approaching:
                direction_factor = 0.3  # 同方向且正在接近，最佳情况
            elif is_same_direction or is_idle:
                direction_factor = 0.6  # 同方向或空闲
            
            # 优先处理高层下行请求，减少高层乘客等待时间
            priority_factor = 1.0
            if direction == "down" and floor.floor > self.max_floor * 0.7:
                priority_factor = 0.7  # 高层下行请求优先级提升
            
            # 当前电梯的请求数量
            request_count = len(self.elevator_up_requests[elevator.id]) + len(self.elevator_down_requests[elevator.id])
            
            # 综合得分
            score = distance * direction_factor * priority_factor + elevator.load_factor * 15 + request_count * 0.8
            
            # 更新最佳电梯
            if score < best_score:
                best_score = score
                best_elevator = elevator
        
        return best_elevator
    
    def _update_elevator_target(self, elevator: ProxyElevator) -> None:
        """根据当前请求更新电梯的目标楼层 - 优化版本"""
        current_floor = elevator.current_floor
        direction = self.elevator_directions[elevator.id]
        
        # 收集所有请求楼层和电梯内部乘客的目标楼层
        target_floors = set()
        
        # 添加电梯内部乘客的目标楼层
        if hasattr(elevator, 'pressed_floors'):
            target_floors.update(elevator.pressed_floors)
        
        # 添加外部请求楼层（LOOK算法：先处理当前方向所有请求）
        if direction == "up":
            # 先添加当前方向的所有请求
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
                    # LOOK算法：选择最远的上方目标，而不是最近的
                    next_floor = max(above_targets)
                else:
                    # 如果当前方向没有更高的目标，改变方向并选择最低目标
                    next_floor = min(target_floors)
                    self.elevator_directions[elevator.id] = "down"
            else:
                # 在当前楼层之下的最近目标楼层
                below_targets = [f for f in target_floors if f < current_floor]
                if below_targets:
                    # LOOK算法：选择最远的下方目标，而不是最近的
                    next_floor = min(below_targets)
                else:
                    # 如果当前方向没有更低的目标，改变方向并选择最高目标
                    next_floor = max(target_floors)
                    self.elevator_directions[elevator.id] = "up"
            
            # 检查是否需要发送命令（避免重复命令）
            if elevator.id not in self.last_elevator_target or self.last_elevator_target[elevator.id] != next_floor:
                # 设置电梯目标
                elevator.go_to_floor(next_floor)
                self.last_elevator_target[elevator.id] = next_floor
    
    def _ensure_elevator_has_target(self, elevator: ProxyElevator) -> None:
        """确保电梯始终有目标楼层"""
        # 如果电梯没有目标或者已经到达目标，更新目标
        if elevator.is_idle:
            self._update_elevator_target(elevator)


if __name__ == "__main__":
    try:
        print("\n" + "=" * 60)
        print("🚀 启动基于LOOK算法的电梯调度系统")
        print("=" * 60)
        # 创建电梯调度器实例并启动
        planner = ElevatorPlanner(debug=True)
        planner.start()
    except KeyboardInterrupt:
        print("\n🛑 电梯调度系统已被用户中断")
    except Exception as e:
        print(f"\n❌ 电梯调度系统启动失败: {e}")
        import traceback
        traceback.print_exc()
