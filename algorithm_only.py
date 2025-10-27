#!/usr/bin/env python3
"""
智能电梯调度算法 - 纯算法模式
只负责控制逻辑，不提供GUI
"""
import os
import random
from typing import List, Dict, Set, Optional
from collections import defaultdict

from elevator_saga.client.base_controller import ElevatorController
from elevator_saga.client.proxy_models import ProxyElevator, ProxyFloor, ProxyPassenger
from elevator_saga.core.models import Direction, SimulationEvent


class IntelligentDispatchController(ElevatorController):
    """
    智能调度算法控制器
    结合了分区策略、SCAN算法和智能派梯的高级调度系统
    设置环境变量 ELEVATOR_CLIENT_TYPE=algorithm 时使用
    """
    
    def __init__(self, server_url: str = "http://127.0.0.1:8000", debug: bool = False):
        super().__init__(server_url, debug)
        
        # 状态管理 - 整合两版优点
        self.unit_state: Dict[int, str] = {}
        self.unit_heading: Dict[int, str] = {}
        self.service_queue: Dict[int, List[int]] = {}
        self.passenger_registry: Dict[int, Dict[int, int]] = {}
        self.elevator_goals: Dict[int, Dict[int, int]] = {}  # 从controller.py借鉴
        
        # 请求队列管理 - 精确跟踪每个楼层的上下行请求
        self.request_queue: List[List[bool]] = []  # [floor][direction] 0=up, 1=down
        self.pending_calls = {"up": set(), "down": set()}
        
        # 基本参数
        self.total_levels = 0
        self.unit_capacity = 10
        self.zone_assignment: Dict[int, tuple] = {}  # 分区策略
        
        # 统计数据
        self.total_energy = 0  # 总能耗
        self.move_count = defaultdict(int)  # 每台电梯移动次数
        self.user_data = {}  # 记录所有乘客信息
        
        if debug:
            print("[算法] 智能调度算法已启动")

    def on_init(self, elevators: List[ProxyElevator], floors: List[ProxyFloor]) -> None:
        """初始化"""
        self.total_levels = len(floors) - 1
        self.building_floors = floors
        self.elevator_fleet = elevators
        
        # 初始化请求队列
        self.request_queue = [[False, False] for _ in range(len(floors))]
        
        if self.debug:
            print(f"[算法] 系统初始化 | {len(elevators)}台电梯 | {len(floors)}层楼")
        
        for idx, unit in enumerate(elevators):
            self.unit_state[unit.id] = "idle"
            self.unit_heading[unit.id] = "none"
            self.service_queue[unit.id] = []
            self.passenger_registry[unit.id] = {}
            self.elevator_goals[unit.id] = {}
            
            # 计算初始位置和服务区域
            home_level = self._calculate_home_position(idx, len(elevators))
            self.zone_assignment[unit.id] = self._get_service_zone(idx, len(elevators))
            
            # 移动到初始位置 - 随机分散电梯
            if random.random() < 0.3:  # 30%概率使用随机分散
                target_floor = random.randint(0, len(floors) - 1)
                unit.go_to_floor(target_floor, immediate=True)
                if self.debug:
                    print(f"[算法] 电梯{idx + 1} 随机初始化 @ F{target_floor}")
            else:  # 70%概率使用分区均匀分布
                unit.go_to_floor(home_level, immediate=True)
                if self.debug:
                    print(f"[算法] 电梯{idx + 1} 分区初始化 @ F{home_level}, 区域: {self.zone_assignment[unit.id]}")

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
        # 增加区域重叠，避免边界问题
        overlap = max(1, int(zone_size * 0.1))
        adjusted_start = max(0, start - overlap)
        adjusted_end = min(self.total_levels, end + overlap)
        return (adjusted_start, adjusted_end)

    def on_event_execute_start(self, tick: int, events: List[SimulationEvent], 
                              elevators: List[ProxyElevator], floors: List[ProxyFloor]) -> None:
        """每个tick开始时，检查未服务请求并智能派遣idle电梯"""
        # 找出所有request的楼层
        request_floors = []
        for f in range(len(self.request_queue)):
            if self.request_queue[f][0] or self.request_queue[f][1]:
                request_floors.append(f)
        
        if not request_floors:
            return
        
        # 获取所有非idle电梯的目标楼层
        target_floors = set()
        for e in elevators:
            if not e.is_idle and hasattr(e, 'target_floor'):
                target_floors.add(e.target_floor)
        
        # 找出没有电梯去的request楼层
        unserved_requests = [f for f in request_floors if f not in target_floors]
        
        idle_elevators = [e for e in elevators if e.is_idle]
        for elevator in idle_elevators:
            if unserved_requests:
                # 结合区域和距离选择最优电梯
                best_score = -1
                best_floor = unserved_requests[0]
                
                for floor in unserved_requests:
                    # 计算距离和区域匹配度
                    distance = abs(elevator.current_floor - floor)
                    zone_start, zone_end = self.zone_assignment[elevator.id]
                    in_zone = 1 if zone_start <= floor <= zone_end else 0.5
                    
                    # 评分：距离越近，区域匹配度越高，分数越高
                    score = (100 - distance * 2) * in_zone
                    
                    if score > best_score:
                        best_score = score
                        best_floor = floor
                
                self._assign_task(elevator, best_floor)
                unserved_requests.remove(best_floor)
                
                if self.debug:
                    print(f"[算法] 事件调度: 电梯{elevator.id + 1} 响应 F{best_floor}")

    def on_passenger_call(self, passenger: ProxyPassenger, floor: ProxyFloor, direction: str) -> None:
        """处理呼叫 - 智能派梯"""
        call_floor = floor.floor
        direction_idx = 0 if direction == "up" else 1
        
        # 更新请求队列
        self.request_queue[call_floor][direction_idx] = True
        self.pending_calls[direction].add(floor.floor)
        
        # 记录乘客信息
        self.user_data[passenger.id] = {
            'origin': passenger.origin,
            'destination': passenger.destination,
            'arrive_tick': passenger.arrive_tick,
            'direction': direction
        }
        
        if self.debug:
            print(f"[算法] 新呼叫 @ F{floor.floor} → {direction}")
        
        # 智能派梯
        self._intelligent_dispatch(floor.floor, direction)

    def _intelligent_dispatch(self, target_floor: int, direction: str):
        """智能派梯算法 - 综合评分"""
        candidates = []
        
        for unit in self.elevator_fleet:
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
        """计算派梯评分 - 优化版"""
        score = 0.0
        state = self.unit_state[unit.id]
        
        # 空闲电梯 - 距离越近分数越高，考虑区域因素
        if state == "idle":
            distance = abs(unit.current_floor - target_floor)
            score = 100 - distance * 2
            
            # 在服务区域内加分
            zone_start, zone_end = self.zone_assignment[unit.id]
            if zone_start <= target_floor <= zone_end:
                score += 50
        
        # 运行中电梯 - 顺路加分，优化评分计算
        elif state == "moving":
            heading = self.unit_heading[unit.id]
            if heading == direction:
                # 同方向且在路径上
                if (heading == "up" and unit.current_floor < target_floor) or \
                   (heading == "down" and unit.current_floor > target_floor):
                    distance = abs(unit.current_floor - target_floor)
                    score = 80 - distance
                    
                    # 负载因子 - 越空越好
                    load_factor = min(1.0, len(unit.passengers) / self.unit_capacity)
                    score *= (1 - load_factor * 0.5)
                    
                    # 距离当前目标越近，接新任务的优先级越低
                    if hasattr(unit, 'target_floor') and unit.target_floor:
                        progress = min(1.0, distance / max(1, abs(unit.current_floor - unit.target_floor)))
                        score *= (1 + progress * 0.3)
        
        return score

    def _assign_task(self, unit: ProxyElevator, target_floor: int):
        """分配任务"""
        if target_floor not in self.service_queue[unit.id]:
            self.service_queue[unit.id].append(target_floor)
        
        if self.unit_state[unit.id] == "idle":
            self.unit_state[unit.id] = "moving"
            self._execute_next(unit)

    def _execute_next(self, unit: ProxyElevator):
        """执行下一个任务 - 优化的SCAN算法"""
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
        # 更新电梯状态
        self.unit_state[elevator.id] = "moving"
        self.unit_heading[elevator.id] = direction
        
        # 记录移动次数（用于能耗计算）
        if int(from_pos) != int(to_pos):
            self.move_count[elevator.id] += 1
            
            # 1-3号电梯能耗为1，4号电梯能耗为2
            energy = 2 if elevator.id == 3 else 1
            # 考虑负载对能耗的影响
            passenger_count = len(elevator.passengers)
            load_factor = min(1.0, passenger_count / self.unit_capacity)
            energy *= (1 + load_factor * 0.3)  # 载客时能耗增加
            
            self.total_energy += energy

    def on_elevator_stopped(self, elevator: ProxyElevator, floor: ProxyFloor) -> None:
        """电梯停靠 - 整合两版优点的智能决策"""
        current = elevator.current_floor
        direction = elevator.last_tick_direction if hasattr(elevator, 'last_tick_direction') else Direction.UP
        
        # 更新请求队列：直接根据floor的队列状态设置
        self.request_queue[current][0] = len(floor.up_queue) > 0
        self.request_queue[current][1] = len(floor.down_queue) > 0
        
        # 从服务队列中移除当前楼层
        if current in self.service_queue[elevator.id]:
            self.service_queue[elevator.id].remove(current)
        
        # 清除对应的呼叫
        heading = self.unit_heading[elevator.id]
        if heading in self.pending_calls:
            self.pending_calls[heading].discard(current)
        
        self.unit_state[elevator.id] = "loading"
        
        if self.debug:
            print(f"[算法] 电梯{elevator.id + 1} 停靠 @ F{floor.floor}")
        
        # 空电梯特殊处理
        if len(elevator.passengers) == 0:
            up_count = len(floor.up_queue) if current < self.total_levels else 0
            down_count = len(floor.down_queue) if current > 0 else 0
            
            # 优先根据当前方向处理请求
            if direction == Direction.UP:
                if up_count > 0:
                    elevator.go_to_floor(current + 1)
                    self.unit_heading[elevator.id] = "up"
                    return
                elif down_count > 0:
                    elevator.go_to_floor(current - 1)
                    self.unit_heading[elevator.id] = "down"
                    return
            elif direction == Direction.DOWN:
                if down_count > 0:
                    elevator.go_to_floor(current - 1)
                    self.unit_heading[elevator.id] = "down"
                    return
                elif up_count > 0:
                    elevator.go_to_floor(current + 1)
                    self.unit_heading[elevator.id] = "up"
                    return
            
            # 处理当前楼层剩余请求
            if up_count > 0 or down_count > 0:
                if up_count > down_count:
                    elevator.go_to_floor(current + 1)
                    self.unit_heading[elevator.id] = "up"
                else:
                    elevator.go_to_floor(current - 1)
                    self.unit_heading[elevator.id] = "down"
                return
            
            # 寻找其他楼层的request
            request_floors = [f for f in range(len(self.request_queue)) 
                             if f != current and (self.request_queue[f][0] or self.request_queue[f][1])]
            if request_floors:
                # 结合距离和区域选择最优楼层
                best_score = -1
                best_floor = request_floors[0]
                
                for f in request_floors:
                    distance = abs(f - current)
                    zone_start, zone_end = self.zone_assignment[elevator.id]
                    in_zone = 1 if zone_start <= f <= zone_end else 0.5
                    score = (100 - distance * 2) * in_zone
                    
                    if score > best_score:
                        best_score = score
                        best_floor = f
                
                elevator.go_to_floor(best_floor)
                if best_floor > current:
                    self.unit_heading[elevator.id] = "up"
                else:
                    self.unit_heading[elevator.id] = "down"
                return
        
        # 获取候选楼层 - 整合了两版算法的优点
        candidates = []
        
        # 1. 电梯内乘客目的地
        my_goals = self.elevator_goals.get(elevator.id, {})
        if my_goals:
            dests = [d for d in my_goals.values() if d != current]
            if direction == Direction.UP:
                dests = [d for d in dests if d > current]
                if dests:
                    candidates.append(min(dests))
            elif direction == Direction.DOWN:
                dests = [d for d in dests if d < current]
                if dests:
                    candidates.append(max(dests))
        
        # 2. 服务队列中的目标
        if self.service_queue[elevator.id]:
            if direction == Direction.UP:
                upper = [f for f in self.service_queue[elevator.id] if f > current]
                if upper:
                    candidates.append(min(upper))
            elif direction == Direction.DOWN:
                lower = [f for f in self.service_queue[elevator.id] if f < current]
                if lower:
                    candidates.append(max(lower))
        
        # 3. 同方向request楼层
        request_floors = []
        for f in range(len(self.request_queue)):
            if self.request_queue[f][0] or self.request_queue[f][1]:
                request_floors.append(f)
        
        if direction == Direction.UP:
            above = [f for f in request_floors if f > current]
            if above:
                candidates.append(min(above))
        elif direction == Direction.DOWN:
            below = [f for f in request_floors if f < current]
            if below:
                candidates.append(max(below))
        
        # 选择最优目标
        if candidates:
            # 去重并根据距离排序
            unique_candidates = list(set(candidates))
            distances = [(abs(f - current), f) for f in unique_candidates]
            distances.sort()
            target_floor = distances[0][1]
            
            elevator.go_to_floor(target_floor)
            if target_floor > current:
                self.unit_heading[elevator.id] = "up"
            else:
                self.unit_heading[elevator.id] = "down"
        else:
            # 无任务时设置为空闲
            self.unit_state[elevator.id] = "idle"
            self.unit_heading[elevator.id] = "none"

    def on_passenger_board(self, elevator: ProxyElevator, passenger: ProxyPassenger) -> None:
        """乘客登梯 - 整合两版记录"""
        # 记录乘客目的地（两版都使用）
        self.passenger_registry[elevator.id][passenger.id] = passenger.destination
        self.elevator_goals[elevator.id][passenger.id] = passenger.destination
        
        # 添加目的地到队列
        if passenger.destination not in self.service_queue[elevator.id]:
            self.service_queue[elevator.id].append(passenger.destination)
        
        if self.debug:
            print(f"[算法] 乘客登梯{elevator.id + 1} → F{passenger.destination}")

    def on_passenger_alight(self, elevator: ProxyElevator, passenger: ProxyPassenger, floor: ProxyFloor) -> None:
        """乘客离梯 - 整合两版清理"""
        # 标记乘客完成
        if passenger.id in self.user_data:
            self.user_data[passenger.id]['completed'] = True
            self.user_data[passenger.id]['completed_tick'] = self.tick if hasattr(self, 'tick') else 0
        
        # 移除乘客目的地记录
        if passenger.id in self.passenger_registry[elevator.id]:
            del self.passenger_registry[elevator.id][passenger.id]
        
        if passenger.id in self.elevator_goals[elevator.id]:
            del self.elevator_goals[elevator.id][passenger.id]
        
        # 如果到达目的地，从服务队列中移除
        if floor.floor in self.service_queue[elevator.id]:
            self.service_queue[elevator.id].remove(floor.floor)

    def on_elevator_idle(self, elevator: ProxyElevator) -> None:
        """电梯空闲 - 智能处理"""
        current = elevator.current_floor
        
        # 清空服务队列
        self.service_queue[elevator.id].clear()
        self.unit_state[elevator.id] = "idle"
        
        # 如果当前楼层有request，优先处理
        if self.request_queue[current][0] and current < self.total_levels:  # up
            elevator.go_to_floor(current + 1)
            self.unit_heading[elevator.id] = "up"
            self.unit_state[elevator.id] = "moving"
            return
        elif self.request_queue[current][1] and current > 0:  # down
            elevator.go_to_floor(current - 1)
            self.unit_heading[elevator.id] = "down"
            self.unit_state[elevator.id] = "moving"
            return
        
        # 寻找其他楼层的request
        waiting = []
        for f in range(len(self.request_queue)):
            if f != current and (self.request_queue[f][0] or self.request_queue[f][1]):
                waiting.append(f)
        
        if waiting:
            # 结合距离和区域选择最优楼层
            best_score = -1
            best_floor = waiting[0]
            
            for f in waiting:
                distance = abs(f - current)
                zone_start, zone_end = self.zone_assignment[elevator.id]
                in_zone = 1 if zone_start <= f <= zone_end else 0.5
                score = (100 - distance * 2) * in_zone
                
                if score > best_score:
                    best_score = score
                    best_floor = f
            
            elevator.go_to_floor(best_floor)
            self.unit_heading[elevator.id] = "up" if best_floor > current else "down"
            self.unit_state[elevator.id] = "moving"
        else:
            # 无请求时，返回区域中心
            zone_start, zone_end = self.zone_assignment[elevator.id]
            zone_center = (zone_start + zone_end) // 2
            if abs(current - zone_center) > 2:  # 只有距离大于2层时才返回
                elevator.go_to_floor(zone_center)
                self.unit_heading[elevator.id] = "up" if zone_center > current else "down"
                self.unit_state[elevator.id] = "moving"
            else:
                self.unit_heading[elevator.id] = "none"

    def on_elevator_passing_floor(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        """经过楼层 - 可扩展接口"""
        pass

    def on_elevator_approaching(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        """接近楼层 - 可扩展接口"""
        pass

    def on_event_execute_end(self, tick, events, elevators, floors):
        """事件执行结束 - 记录时间戳"""
        self.tick = tick

    def on_stop(self):
        """停止时输出统计信息"""
        if self.debug:
            print("\n[算法] 调度算法停止，统计信息:")
            print(f"  总能耗: {self.total_energy:.2f}")
            print("  电梯移动次数:")
            for elevator_id, count in sorted(self.move_count.items()):
                print(f"    电梯{elevator_id + 1}: {count}次")
            # 计算完成率
            total_passengers = len(self.user_data)
            completed_passengers = sum(1 for p in self.user_data.values() if p.get('completed', False))
            completion_rate = (completed_passengers / total_passengers * 100) if total_passengers > 0 else 0
            print(f"  乘客完成率: {completed_passengers}/{total_passengers} ({completion_rate:.1f}%)")


def main():
    """主函数"""
    # 设置环境变量
    os.environ['ELEVATOR_CLIENT_TYPE'] = 'algorithm'
    
    controller = IntelligentDispatchController(
        server_url="http://127.0.0.1:8000",
        debug=True
    )
    
    print("[算法] 启动优化版智能调度控制器...")
    try:
        controller.start()
    except KeyboardInterrupt:
        print("\n[CTRL+C] 正在优雅停止...")
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        # 确保清理，无论正常退出、异常还是 Ctrl+C
        try:
            controller.on_stop()
        except Exception:
            pass


if __name__ == '__main__':
    import sys
    main()


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
