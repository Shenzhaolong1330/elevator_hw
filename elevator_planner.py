#!/usr/bin/env python3
"""
优化的SCAN电梯调度算法 - 智能响应版（优先顺路）
电梯在两端之间来回运行，优先响应顺路请求
运送结束后立即停在当前楼层进入休息状态，优先响应新请求
智能响应逻辑：优先顺路工作电梯（包括有载电梯），其次休息电梯
"""
from typing import Dict, List, Set

from elevator_saga.client.base_controller import ElevatorController
from elevator_saga.client.proxy_models import ProxyElevator, ProxyFloor, ProxyPassenger
from elevator_saga.core.models import Direction, SimulationEvent


class OptimizedScanController(ElevatorController):
    """
    优化的SCAN电梯调度算法 - 智能响应版
    有请求时：优先顺路工作电梯（包括有载电梯），其次休息电梯
    无请求时：立即停在当前楼层进入休息状态，优先响应新请求
    """

    def __init__(self, server_url: str = "http://127.0.0.1:8000", debug: bool = False):
        """初始化控制器"""
        super().__init__(server_url, debug)
        self.elevator_directions: Dict[int, str] = {}  # 记录每个电梯的当前方向
        self.elevator_target_floors: Dict[int, Set[int]] = {}  # 记录每个电梯的目标楼层集合
        self.passenger_destinations: Dict[int, Dict[int, int]] = {}  # 记录乘客目的地
        self.max_floor = 0  # 最大楼层数
        self.floor_requests: Dict[str, Set[int]] = {"up": set(), "down": set()}  # 记录各方向的楼层请求
        self.elevator_resting_floors: Dict[int, int] = {}  # 记录电梯的休息楼层（初始位置）
        self.elevator_states: Dict[int, str] = {}  # 记录电梯状态: 'resting', 'scanning'
        
        # 新增：与前端交互和运行时状态（不改变现有调度逻辑）
        self.elevators: List[ProxyElevator] = []
        self.all_passengers: List[ProxyPassenger] = []  # 用于可视化/诊断
        self.current_tick: int = 0
        self.events_log = []
        self.backend_url = "http://127.0.0.1:5000"
        self.backend_available = self._check_backend()

    def _check_backend(self) -> bool:
        """检查可视化后端可用性（保持轻量，不影响主逻辑）"""
        try:
            import requests
            resp = requests.get(f"{self.backend_url}/health", timeout=1)
            return resp.status_code == 200
        except Exception:
            return False

    def _send_state_to_backend(self, elevators: List[ProxyElevator]) -> None:
        """向可视化后端发送当前状态（容错，不影响主逻辑）"""
        if not self.backend_available:
            return
        try:
            import requests
            elevator_data = []
            for e in elevators:
                elevator_data.append({
                    "id": e.id,
                    "current_floor": round(e.current_floor_float, 1),
                    "target_floor": e.target_floor,
                    "passengers": len(e.passengers),
                    "direction": e.target_floor_direction.value,
                    "capacity": 8
                })
            events_data = [{"type": ev.type.value, "desc": str(ev)} for ev in self.events_log[-10:]]
            passengers_data = [{"id": p.id, "origin": p.origin, "destination": p.destination} for p in self.all_passengers[-50:]]
            payload = {
                "tick": self.current_tick,
                "elevators": elevator_data,
                "events": events_data,
                "passengers": passengers_data,
                "max_floor": self.max_floor
            }
            requests.post(f"{self.backend_url}/api/update", json=payload, timeout=1)
        except Exception:
            # 上报失败不影响主流程
            pass

    def on_init(self, elevators: List[ProxyElevator], floors: List[ProxyFloor]) -> None:
        """初始化优化的SCAN电梯算法"""
        print("    优化的SCAN电梯算法初始化 - 优先顺路版")
        print(f"   管理 {len(elevators)} 部电梯")
        print(f"   服务 {len(floors)} 层楼")
        
        # 获取最大楼层数
        self.max_floor = len(floors) - 1
        
        # 初始化每个电梯的状态
        for i, elevator in enumerate(elevators):
            self.elevator_directions[elevator.id] = "up"  # 初始方向向上
            self.elevator_target_floors[elevator.id] = set()
            self.passenger_destinations[elevator.id] = {}
            self.elevator_states[elevator.id] = 'resting'  # 初始状态为休息
            
            # 计算初始休息楼层 - 将电梯均匀分布在楼层上
            self.elevator_resting_floors[elevator.id] = self._calculate_resting_floor(i, len(elevators))
            
            # 移动到初始休息楼层
            elevator.go_to_floor(self.elevator_resting_floors[elevator.id], immediate=True)
            print(f"   电梯 E{elevator.id} 初始休息位置: F{self.elevator_resting_floors[elevator.id]}")

        # 保持对电梯列表的引用，供调度/唤醒使用
        self.elevators = elevators

    def _calculate_resting_floor(self, elevator_index: int, total_elevators: int) -> int:
        """计算电梯的初始休息楼层，确保均匀分布"""
        if total_elevators == 1:
            return self.max_floor // 2  # 只有一部电梯时停在中间
        
        # 将楼层范围均匀分配给所有电梯
        segment_size = (self.max_floor + 1) / total_elevators
        return min(int(elevator_index * segment_size + segment_size / 2), self.max_floor)

    def on_event_execute_start(
        self, tick: int, events: List[SimulationEvent], elevators: List[ProxyElevator], floors: List[ProxyFloor]
    ) -> None:
        """事件执行前的回调"""
        # 同步运行时状态以便输出/上报
        self.current_tick = tick
        self.events_log = events
        self.elevators = elevators
        
        if events:
            event_types = [e.type.value for e in events]
            if any(event in event_types for event in ['passenger_call', 'elevator_idle', 'elevator_stopped']):
                print(f"Tick {tick}: 处理 {len(events)} 个事件 {event_types}")
        
        # 显示电梯状态（保持原有输出格式，前端可能解析）
        for elevator in elevators:
            passenger_count = len(elevator.passengers)
            direction = self.elevator_directions.get(elevator.id, "up")
            state = self.elevator_states.get(elevator.id, "resting")
            target_info = f"目标:{list(self.elevator_target_floors.get(elevator.id, set()))}" if self.elevator_target_floors.get(elevator.id) else "无目标"
            print(f"   E{elevator.id}[{direction}|{state}] 在 F{elevator.current_floor} {target_info} 乘客:{passenger_count}")

    def on_event_execute_end(
        self, tick: int, events: List[SimulationEvent], elevators: List[ProxyElevator], floors: List[ProxyFloor]
    ) -> None:
        """事件执行后的回调"""
        # 保持原有的调度逻辑
        pass
        
        # 向前端/可视化后端发送状态（容错）
        self._send_state_to_backend(elevators)

    def on_passenger_call(self, passenger: ProxyPassenger, floor: ProxyFloor, direction: str) -> None:
        """
        乘客呼叫时的回调
        记录楼层请求，智能选择电梯响应
        """
        # 保留原有输出
        print(f" 乘客 {passenger.id} 在 F{floor.floor} 请求 {direction} 方向")
        self.floor_requests[direction].add(floor.floor)
        print(f"   当前请求 - 上行: {sorted(self.floor_requests['up'])}, 下行: {sorted(self.floor_requests['down'])}")
        
        # 记录乘客（供可视化/诊断使用）
        try:
            self.all_passengers.append(passenger)
        except Exception:
            # 兼容性保护，不阻塞主逻辑
            pass
        
        # 智能选择电梯响应请求
        self._smart_assign_elevator(floor.floor, direction)

    def _smart_assign_elevator(self, request_floor: int, direction: str) -> None:
        """
        智能分配策略：优先顺路的工作电梯（包括有载电梯），其次休息电梯
        """
        # 首先寻找可以响应的工作中电梯（顺路接人，包括有载电梯）
        working_candidate = self._find_working_elevator_candidate(request_floor, direction)
        if working_candidate:
            benefit, elevator_id, elevator, passenger_count = working_candidate
            load_info = "空载" if passenger_count == 0 else f"有载({passenger_count}人)"
            print(f"   智能响应: E{elevator_id} {load_info} 顺路响应 F{request_floor} 的请求 (节省距离: {benefit}层)")
            self._redirect_elevator(elevator, request_floor, direction)
            return
        
        # 没有顺路工作电梯时，寻找休息电梯
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
        
        print(f"   无合适电梯可用，等待扫描中的电梯自然处理请求")

    def _find_working_elevator_candidate(self, request_floor: int, direction: str):
        """
        寻找可以响应新请求的工作中电梯（包括有载电梯）
        """
        best_candidate = None
        best_benefit = 0
        
        for elevator in self.elevators:
            elevator_id = elevator.id
            
            # 只考虑工作中的电梯（不限制是否空载）
            if self.elevator_states[elevator_id] != 'scanning':
                continue
            
            current_floor = elevator.current_floor
            current_direction = self.elevator_directions[elevator_id]
            current_targets = self.elevator_target_floors[elevator_id]
            
            if not current_targets:
                continue
                
            # 获取当前主要目标
            current_target = min(current_targets) if current_direction == 'up' else max(current_targets)
            
            # 检查响应条件：
            # 1. 方向必须匹配
            direction_ok = self._is_direction_matching(current_floor, request_floor, current_direction)
            # 2. 新请求必须在路径上（不会导致反向）
            on_the_way = self._is_on_the_way(current_floor, current_target, request_floor, current_direction)
            
            if direction_ok and on_the_way:
                # 计算响应收益（节省的距离）
                distance_to_target = abs(current_floor - current_target)
                distance_to_request = abs(current_floor - request_floor)
                benefit = distance_to_target - distance_to_request
                
                # 只考虑有实际收益的情况（节省距离>0）
                if benefit > 0 and benefit > best_benefit:
                    best_benefit = benefit
                    best_candidate = (benefit, elevator_id, elevator, len(elevator.passengers))
        
        return best_candidate

    def _is_direction_matching(self, current_floor: int, request_floor: int, current_direction: str) -> bool:
        """检查方向是否匹配"""
        if current_direction == "up":
            return request_floor >= current_floor
        else:  # direction == "down"
            return request_floor <= current_floor

    def _is_on_the_way(self, current_floor: int, current_target: int, request_floor: int, direction: str) -> bool:
        """检查新请求是否在当前路径上"""
        if direction == "up":
            return current_floor <= request_floor <= current_target
        else:  # direction == "down"
            return current_floor >= request_floor >= current_target

    def _redirect_elevator(self, elevator: ProxyElevator, request_floor: int, direction: str) -> None:
        """重定向电梯响应新请求"""
        elevator_id = elevator.id
        
        # 保留原有目标，只是增加新目标
        # 这样电梯会在F3接人后继续前往F5
        self.elevator_target_floors[elevator_id].add(request_floor)
        
        # 不需要清空原有目标，也不需要改变方向
        # 电梯会自动按SCAN算法处理所有目标
        
        print(f"    E{elevator_id} 将响应 F{request_floor} 的请求")

    def _wake_up_elevator(self, elevator: ProxyElevator, request_floor: int, direction: str) -> None:
        """唤醒休息电梯"""
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

    def on_elevator_idle(self, elevator: ProxyElevator) -> None:
        """
        电梯空闲时的回调
        检查是否有请求，没有则立即进入休息状态
        """
        print(f" 电梯 E{elevator.id} 在 F{elevator.current_floor} 层空闲")
        
        # 清空目标楼层集合
        self.elevator_target_floors[elevator.id].clear()
        
        # 检查是否还有未处理的请求
        if self._has_pending_requests() or self._has_internal_requests(elevator):
            # 有请求，继续SCAN算法
            self.elevator_states[elevator.id] = 'scanning'
            self._assign_next_floor(elevator)
        else:
            # 无请求，立即在当前楼层进入休息状态
            self._enter_resting_state(elevator)

    def _enter_resting_state(self, elevator: ProxyElevator) -> None:
        """让电梯进入休息状态"""
        self.elevator_states[elevator.id] = 'resting'
        current_floor = elevator.current_floor
        self.elevator_resting_floors[elevator.id] = current_floor
        print(f"   💤 电梯 E{elevator.id} 在 F{current_floor} 进入休息状态，等待新请求")

    def on_elevator_stopped(self, elevator: ProxyElevator, floor: ProxyFloor) -> None:
        """
        电梯停靠时的回调
        处理当前楼层的请求，并决定下一个目标
        """
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
        
        # 检查是否还有任务
        if self._has_pending_requests() or self._has_internal_requests(elevator):
            # 还有任务，继续SCAN算法
            self.elevator_states[elevator.id] = 'scanning'
            self._assign_next_floor(elevator)
        else:
            # 所有任务完成，立即进入休息状态
            print(f"    电梯 E{elevator.id} 完成所有任务，在 F{current_floor} 进入休息状态")
            self._enter_resting_state(elevator)

    def _has_pending_requests(self) -> bool:
        """检查是否有未处理的请求"""
        return bool(self.floor_requests["up"] or self.floor_requests["down"])

    def _has_internal_requests(self, elevator: ProxyElevator) -> bool:
        """检查电梯内部是否有乘客请求"""
        return bool(self.passenger_destinations[elevator.id])

    def _assign_next_floor(self, elevator: ProxyElevator) -> None:
        """
        SCAN算法的核心：为电梯分配下一个目标楼层
        """
        current_floor = elevator.current_floor
        direction = self.elevator_directions[elevator.id]
        
        # 获取当前方向上的所有请求（包括内部选层和外部呼叫）
        target_floors = self._get_floors_in_direction(elevator, direction)
        
        if target_floors:
            # 在当前方向上有请求，选择最近的一个
            if direction == "up":
                next_floor = min(target_floors)
            else:  # direction == "down"
                next_floor = max(target_floors)
            
            print(f"   SCAN决策: E{elevator.id} {direction}方向 -> F{next_floor}")
            elevator.go_to_floor(next_floor)
            self.elevator_target_floors[elevator.id].add(next_floor)
        else:
            # 当前方向没有请求，改变方向
            new_direction = "down" if direction == "up" else "up"
            print(f"   SCAN决策: E{elevator.id} 改变方向 {direction} -> {new_direction}")
            self.elevator_directions[elevator.id] = new_direction
            
            # 在新方向上寻找目标
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
                # 两个方向都没有请求，进入休息状态
                print(f"   电梯 E{elevator.id} 无任务可执行")
                self._enter_resting_state(elevator)

    def _get_floors_in_direction(self, elevator: ProxyElevator, direction: str) -> Set[int]:
        """
        获取指定方向上所有需要停靠的楼层
        包括：内部选层 + 外部呼叫
        """
        current_floor = elevator.current_floor
        target_floors = set()
        
        # 内部选层请求（从我们记录的乘客目的地中获取）
        elevator_id = elevator.id
        for passenger_id, destination in self.passenger_destinations[elevator_id].items():
            if ((direction == "up" and destination > current_floor) or
                (direction == "down" and destination < current_floor)):
                target_floors.add(destination)
        
        # 外部呼叫请求
        if direction == "up":
            # 上行：当前楼层以上的上行和下行请求
            for floor_num in self.floor_requests["up"] | self.floor_requests["down"]:
                if floor_num > current_floor:
                    target_floors.add(floor_num)
        else:  # direction == "down"
            # 下行：当前楼层以下的上行和下行请求
            for floor_num in self.floor_requests["up"] | self.floor_requests["down"]:
                if floor_num < current_floor:
                    target_floors.add(floor_num)
        
        return target_floors

    def on_passenger_board(self, elevator: ProxyElevator, passenger: ProxyPassenger) -> None:
        """
        乘客上梯时的回调
        记录乘客的目标楼层
        """
        print(f"    乘客{passenger.id} 上 E{elevator.id} (F{elevator.current_floor} -> F{passenger.destination})")
        self.passenger_destinations[elevator.id][passenger.id] = passenger.destination
        
        if self.elevator_states[elevator.id] == 'resting':
            self.elevator_states[elevator.id] = 'scanning'
            print(f"   电梯 E{elevator.id} 因乘客上梯而激活")

    def on_passenger_alight(self, elevator: ProxyElevator, passenger: ProxyPassenger, floor: ProxyFloor) -> None:
        """
        乘客下车时的回调
        移除记录的乘客目的地
        """
        print(f"    乘客{passenger.id} 下 E{elevator.id} 在 F{floor.floor}")
        if passenger.id in self.passenger_destinations[elevator.id]:
            del self.passenger_destinations[elevator.id][passenger.id]

    def on_elevator_passing_floor(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        """电梯经过楼层时的回调"""
        pass

    def on_elevator_approaching(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        """电梯即将到达时的回调"""
        pass

    def on_elevator_move(
        self, elevator: ProxyElevator, from_position: float, to_position: float, direction: str, status: str
    ) -> None:
        """电梯移动时的回调"""
        pass


if __name__ == "__main__":
    algorithm = OptimizedScanController(debug=True)
    algorithm.start()