"""trust_game_code.game

游戏逻辑：管理单局 Prisoner's Dilemma 游戏。

本版本采用“每轮以概率 δ 继续”的框架（几何分布回合数）。
"""

import random
import logging
from typing import Dict, List, Optional, Tuple
from agents import Agent, Action

# 配置游戏日志
game_logger = logging.getLogger("trust_game")
game_logger.setLevel(logging.INFO)
if not game_logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - [GAME] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    console_handler.setFormatter(formatter)
    game_logger.addHandler(console_handler)


class Game:
    """单局游戏管理器"""
    
    def __init__(
        self,
        agent1: Agent,
        agent2: Agent,
        delta: float = 0.9,
        max_rounds: int = 200,
        fixed_rounds: Optional[int] = None,
        rng: Optional[random.Random] = None,
        verbose: bool = False,
        rounds_range: Tuple[int, int] = (1, 200),
        payoff_matrix: Optional[Dict[str, Dict[str, Tuple[float, float]]]] = None
    ):
        """
        初始化游戏
        
        Args:
            agent1: 第一个 agent
            agent2: 第二个 agent
            rounds_range: 回合数范围 (min, max)
            payoff_matrix: Payoff 矩阵，格式为：
                {
                    "cooperate": {
                        "cooperate": (payoff1, payoff2),
                        "defect": (payoff1, payoff2)
                    },
                    "defect": {
                        "cooperate": (payoff1, payoff2),
                        "defect": (payoff1, payoff2)
                    }
                }
                如果为 None，使用默认值：(-1/3, 2/2, 0/0)
        """
        self.agent1 = agent1
        self.agent2 = agent2

        # 兼容旧接口：rounds_range 不再决定总轮数，仅作为“信息占位”传给 agent。
        self.rounds_range = rounds_range

        if not (0.0 <= delta < 1.0):
            raise ValueError(f"delta must be in [0, 1). Got: {delta}")
        if max_rounds < 1:
            raise ValueError(f"max_rounds must be >= 1. Got: {max_rounds}")

        self.delta = delta
        self.max_rounds = max_rounds
        self.fixed_rounds = fixed_rounds
        self.rng = rng or random.Random()
        self.verbose = verbose

        # 实际总回合数在 play() 中产生（δ-继续或 fixed_rounds）。
        self.total_rounds: int = 0
        
        # 默认 payoff 矩阵
        if payoff_matrix is None:
            self.payoff_matrix = {
                "cooperate": {
                    "cooperate": (2.0, 2.0),  # 双方合作
                    "defect": (-1.0, 3.0)     # agent1 合作，agent2 背叛
                },
                "defect": {
                    "cooperate": (3.0, -1.0),  # agent1 背叛，agent2 合作
                    "defect": (0.0, 0.0)      # 双方背叛
                }
            }
        else:
            self.payoff_matrix = payoff_matrix
        
        # 游戏历史
        self.history: List[Dict] = []
        self.agent1_total_payoff = 0.0
        self.agent2_total_payoff = 0.0
    
    def _calculate_payoff(self, action1: Action, action2: Action) -> Tuple[float, float]:
        """
        计算 payoff
        
        Args:
            action1: agent1 的动作
            action2: agent2 的动作
            
        Returns:
            (agent1_payoff, agent2_payoff)
        """
        return self.payoff_matrix[action1][action2]
    
    async def play(self) -> Dict:
        """
        执行游戏
        
        Returns:
            游戏结果字典，包含：
            - agent1_name: agent1 名称
            - agent2_name: agent2 名称
            - total_rounds: 总回合数
            - agent1_total_payoff: agent1 总得分
            - agent2_total_payoff: agent2 总得分
            - history: 每轮历史记录
        """
        # 重置 agents
        self.agent1.reset()
        self.agent2.reset()
        self.history = []
        self.agent1_total_payoff = 0.0
        self.agent2_total_payoff = 0.0
        
        # 记录游戏开始
        if self.verbose:
            print(f"Game Started: {self.agent1.name} vs {self.agent2.name}")
            if self.fixed_rounds is not None:
                print(f"Total Rounds (fixed): {self.fixed_rounds}")
            else:
                print(f"Delta continuation: δ={self.delta:.4f} (max_rounds={self.max_rounds})")
        
        # 第一轮：双方都不知道对手上一轮的动作
        agent1_last_action: Optional[Action] = None
        agent2_last_action: Optional[Action] = None
        
        round_num = 1
        stopped_reason = "unknown"
        while True:
            if self.verbose:
                print(f"\n--- Round {round_num} ---")
            # Agent1 选择动作
            action1 = await self.agent1.choose_action(
                round_num=round_num,
                total_rounds_range=self.rounds_range,
                delta=self.delta,
                opponent_last_action=agent2_last_action,
                payoff_matrix=self.payoff_matrix
            )
            
            # Agent2 选择动作
            action2 = await self.agent2.choose_action(
                round_num=round_num,
                total_rounds_range=self.rounds_range,
                delta=self.delta,
                opponent_last_action=agent1_last_action,
                payoff_matrix=self.payoff_matrix
            )
            
            # 计算 payoff
            payoff1, payoff2 = self._calculate_payoff(action1, action2)
            
            # 记录结果
            self.agent1.record_round(action1, action2, payoff1)
            self.agent2.record_round(action2, action1, payoff2)
            
            self.agent1_total_payoff += payoff1
            self.agent2_total_payoff += payoff2
            
            # 记录历史
            round_record = {
                "round": round_num,
                "agent1_action": action1,
                "agent2_action": action2,
                "agent1_payoff": payoff1,
                "agent2_payoff": payoff2,
                "agent1_total_payoff": self.agent1_total_payoff,
                "agent2_total_payoff": self.agent2_total_payoff
            }
            self.history.append(round_record)
            
            # 记录本轮结果
            if self.verbose:
                print(f"  {self.agent1.name}: {action1.upper()} (payoff: {payoff1:+.1f}, total: {self.agent1_total_payoff:.1f})")
                print(f"  {self.agent2.name}: {action2.upper()} (payoff: {payoff2:+.1f}, total: {self.agent2_total_payoff:.1f})")
            
            # 更新上一轮动作
            agent1_last_action = action1
            agent2_last_action = action2

            # 回合结束：决定是否继续
            if self.fixed_rounds is not None:
                if round_num >= self.fixed_rounds:
                    stopped_reason = "fixed_rounds_reached"
                    break
            else:
                if round_num >= self.max_rounds:
                    stopped_reason = "max_rounds_cap"
                    break
                if self.rng.random() >= self.delta:
                    stopped_reason = "stopped_by_delta"
                    break

            round_num += 1

        self.total_rounds = round_num

        # 记录游戏结束
        if self.verbose:
            print("\n" + "=" * 20)
            print("Game Finished")
            print(f"  {self.agent1.name} Total Payoff: {self.agent1_total_payoff:.2f}")
            print(f"  {self.agent2.name} Total Payoff: {self.agent2_total_payoff:.2f}")
            print("=" * 20 + "\n")
        
        return {
            "agent1_name": self.agent1.name,
            "agent2_name": self.agent2.name,
            "total_rounds": self.total_rounds,
            "rounds_range": self.rounds_range,
            "delta": self.delta,
            "max_rounds": self.max_rounds,
            "fixed_rounds": self.fixed_rounds,
            "stopped_reason": stopped_reason,
            "agent1_total_payoff": self.agent1_total_payoff,
            "agent2_total_payoff": self.agent2_total_payoff,
            "history": self.history
        }

