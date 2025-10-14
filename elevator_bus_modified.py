#!/usr/bin/env python3
"""
修改后的电梯总线控制器
增加功能：将电梯状态实时发送到可视化后端
"""

from typing import List
import requests
import json

from elevator_saga.client.base_controller import ElevatorController
from elevator_saga.client.proxy_models import ProxyElevator, ProxyFloor, ProxyPassenger
from elevator_saga.core.models import Direction, SimulationEvent


class ElevatorBusExampleController(ElevatorController):
    def __init__(self) -> None:
        super().__init__("http://127.0.0.1:8000", True)
        self.all_passengers: List[ProxyPassenger] = []
        self.max_floor = 0
        self.backend_url = "http://127.0.0.1:5000"  # 后端服务地址
        self.current_tick = 0
        self.events_log = []
        
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
        """初始化电梯"""
        self.max_floor = floors[-1].floor
        self.floors = floors
        for i, elevator in enumerate(elevators):
            # 计算目标楼层 - 均匀分布在不同楼层
            target_floor = (i * (len(floors) - 1)) // len(elevators)
            # 立刻移动到目标位置并开始循环
            elevator.go_to_floor(target_floor, immediate=True)
        
        print(f"✅ 初始化完成: {len(elevators)} 个电梯, {self.max_floor} 层楼")

    def on_event_execute_start(
        self, tick: int, events: List[SimulationEvent], elevators: List[ProxyElevator], floors: List[ProxyFloor]
    ) -> None:
        """事件执行开始"""
        self.current_tick = tick
        self.events_log = events
        
        print(f"Tick {tick}: 即将处理 {len(events)} 个事件 {[e.type.value for e in events]}")
        for i in elevators:
            print(
                f"\t{i.id}[{i.target_floor_direction.value},{i.current_floor_float}/{i.target_floor}]"
                + "👦" * len(i.passengers),
                end="",
            )
        print()

    def on_event_execute_end(
        self, tick: int, events: List[SimulationEvent], elevators: List[ProxyElevator], floors: List[ProxyFloor]
    ) -> None:
        """事件执行结束 - 发送数据到可视化后端"""
        self._send_state_to_backend(elevators)

    def on_passenger_call(self, passenger: ProxyPassenger, floor: ProxyFloor, direction: str) -> None:
        """乘客呼叫电梯"""
        self.all_passengers.append(passenger)
        print(f"乘客 {passenger.id} F{floor.floor} 请求 {passenger.origin} -> {passenger.destination} ({direction})")

    def on_elevator_idle(self, elevator: ProxyElevator) -> None:
        """电梯空闲"""
        elevator.go_to_floor(1)

    def on_elevator_stopped(self, elevator: ProxyElevator, floor: ProxyFloor) -> None:
        """电梯停靠"""
        print(f"🛑 电梯 E{elevator.id} 停靠在 F{floor.floor}")
        # BUS调度算法，电梯到达顶层后，立即下降一层
        if elevator.last_tick_direction == Direction.UP and elevator.current_floor == self.max_floor:
            elevator.go_to_floor(elevator.current_floor - 1)
        # 电梯到达底层后，立即上升一层
        elif elevator.last_tick_direction == Direction.DOWN and elevator.current_floor == 0:
            elevator.go_to_floor(elevator.current_floor + 1)
        elif elevator.last_tick_direction == Direction.UP:
            elevator.go_to_floor(elevator.current_floor + 1)
        elif elevator.last_tick_direction == Direction.DOWN:
            elevator.go_to_floor(elevator.current_floor - 1)

    def on_passenger_board(self, elevator: ProxyElevator, passenger: ProxyPassenger) -> None:
        """乘客上电梯"""
        print(f" 乘客{passenger.id} E{elevator.id}⬆️ F{elevator.current_floor} -> F{passenger.destination}")

    def on_passenger_alight(self, elevator: ProxyElevator, passenger: ProxyPassenger, floor: ProxyFloor) -> None:
        """乘客下电梯"""
        print(f" 乘客{passenger.id} E{elevator.id}⬇️ F{floor.floor}")

    def on_elevator_passing_floor(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        pass

    def on_elevator_approaching(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        pass

    def on_elevator_move(
        self, elevator: ProxyElevator, from_position: float, to_position: float, direction: str, status: str
    ) -> None:
        pass


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 启动电梯总线控制系统")
    print("=" * 60)
    algorithm = ElevatorBusExampleController()
    algorithm.start()