"""trust_game_code.agents

Agent 定义：包括 baseline agents 和 LLM agents。

注意：为保证可复现性，本项目尽量避免使用全局 random，改为每个 Agent
持有独立的 random.Random 实例（self.rng）。
"""

import asyncio
import random
import os
import json
import re
import logging
from datetime import datetime
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Literal
from dotenv import load_dotenv
try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

# 加载 .env 文件中的环境变量
load_dotenv()

# 配置日志
def setup_llm_logger(agent_name: str, log_dir: str = "logs") -> logging.Logger:
    """
    为 LLM Agent 设置日志记录器
    
    Args:
        agent_name: Agent 名称
        log_dir: 日志目录
        
    Returns:
        配置好的 logger
    """
    # 创建日志目录
    os.makedirs(log_dir, exist_ok=True)
    
    # 创建 logger
    logger = logging.getLogger(f"llm_agent_{agent_name}")
    logger.setLevel(logging.INFO)
    
    # 避免重复添加 handler
    if logger.handlers:
        return logger
    
    # 文件 handler（保存到文件）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"{agent_name}_{timestamp}.log")
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # 控制台 handler
    # console_handler = logging.StreamHandler()
    # console_handler.setLevel(logging.INFO)
    
    # 格式化
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    # console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    # logger.addHandler(console_handler)
    
    return logger

Action = Literal["cooperate", "defect"]


class Agent(ABC):
    """Agent 基类"""
    
    def __init__(self, name: str, seed: Optional[int] = None):
        """
        初始化 Agent
        
        Args:
            name: Agent 名称
        """
        self.name = name
        # 每个 agent 独立 RNG（避免共享全局 random 导致的耦合与不可复现）
        self.rng = random.Random(seed)
        self.total_payoff = 0.0
        self.action_history: List[Action] = []
        self.opponent_action_history: List[Action] = []
        self.payoff_history: List[float] = []
    
    @abstractmethod
    async def choose_action(
        self,
        round_num: int,
        total_rounds_range: tuple[int, int],
        delta: Optional[float] = None,
        opponent_last_action: Optional[Action] = None,
        payoff_matrix: Optional[Dict[str, Dict[str, tuple[float, float]]]] = None
    ) -> Action:
        """
        选择动作
        
        Args:
            round_num: 当前回合数（从1开始）
            total_rounds_range: 总回合数范围 (min, max)
            opponent_last_action: 对手上一轮的动作（第一轮为 None）
            
        Returns:
            选择的动作："cooperate" 或 "defect"
        """
        pass
    
    def reset(self):
        """重置 agent 状态"""
        self.total_payoff = 0.0
        self.action_history = []
        self.opponent_action_history = []
        self.payoff_history = []
        # 重置对话历史
        self.conversation_history = []
        self.game_initialized = False
        self._system_prompt_logged = False

    def set_seed(self, seed: int):
        """设置该 agent 的随机种子（用于可复现性）。

        说明：历史版本中此文件曾出现重复定义 set_seed 的问题。
        这里统一为“直接 seed 到该 agent 的独立 RNG”。
        """
        self.rng = random.Random(seed)

    def signature(self) -> Dict:
        """用于缓存/复现的稳定签名。

        注意：baseline 命名不改；signature 仅用于区分实现与关键参数。
        """
        return {"name": self.name, "type": self.__class__.__name__}

    @abstractmethod
    def clone(self) -> "Agent":
        """深拷贝一个“新状态”的 agent，用于并发对局。

        clone 必须：
        - 保留同名（name 不变，用于聚合统计）；
        - 复制关键超参数（例如 RandomAgent 的 cooperate_prob，LLMAgent 的 model）；
        - 不共享对局状态（history / conversation_history 等要是新的）。
        """
        raise NotImplementedError
    
    def record_round(
        self,
        action: Action,
        opponent_action: Action,
        payoff: float
    ):
        """
        记录一轮的结果
        
        Args:
            action: 自己的动作
            opponent_action: 对手的动作
            payoff: 本轮获得的 payoff
        """
        self.action_history.append(action)
        self.opponent_action_history.append(opponent_action)
        self.payoff_history.append(payoff)
        self.total_payoff += payoff


class RandomAgent(Agent):
    """随机策略 Agent（baseline）"""
    
    def __init__(self, name: str = "Random", cooperate_prob: float = 0.5):
        """
        初始化随机 Agent
        
        Args:
            name: Agent 名称
            cooperate_prob: 合作的概率（默认 0.5）
        """
        super().__init__(name)
        self.cooperate_prob = cooperate_prob

    def signature(self) -> Dict:
        s = super().signature()
        s.update({"cooperate_prob": self.cooperate_prob})
        return s

    def clone(self) -> "Agent":
        return RandomAgent(name=self.name, cooperate_prob=self.cooperate_prob)
    
    async def choose_action(
        self,
        round_num: int,
        total_rounds_range: tuple[int, int],
        delta: Optional[float] = None,
        opponent_last_action: Optional[Action] = None,
        payoff_matrix: Optional[Dict[str, Dict[str, tuple[float, float]]]] = None
    ) -> Action:
        """随机选择动作"""
        res = "cooperate" if self.rng.random() < self.cooperate_prob else "defect"
        print("=" * 20)
        print(f"[{self.name}] Round {round_num} - Random Agent Response:")
        print(f"  {res.upper()}")
        print("=" * 20)
        return res


class GrimTriggerAgent(Agent):
    """以牙还牙策略 Agent（baseline）"""
    
    def __init__(self, name: str = "Grim Trigger"):
        """
        初始化 Grim Trigger Agent
        
        Args:
            name: Agent 名称
        """
        super().__init__(name)

    def clone(self) -> "Agent":
        # baseline 命名按用户要求保持不变
        return GrimTriggerAgent(name=self.name)
    
    async def choose_action(
        self,
        round_num: int,
        total_rounds_range: tuple[int, int],
        delta: Optional[float] = None,
        opponent_last_action: Optional[Action] = None,
        payoff_matrix: Optional[Dict[str, Dict[str, tuple[float, float]]]] = None
    ) -> Action:
        """
        以牙还牙（Grim Trigger）策略：第一轮合作，之后一直cooperate，如果对手defect，则defect
        """
        res = "cooperate"
        if round_num == 1 or opponent_last_action is None:
            res = "cooperate"
        elif opponent_last_action == "defect" or self.action_history[-1] == "defect":
            res = "defect"

        print("=" * 20)
        print(f"[{self.name}] Round {round_num} - Grim Trigger Agent Response:")
        print(f"  {res.upper()}")
        print("=" * 20)
        return res


class TFTAgent(Agent):
    """复制对手上一轮动作的 Agent"""
    
    def __init__(self, name: str = "TFT"):
        super().__init__(name)

    def clone(self) -> "Agent":
        return TFTAgent(name=self.name)
    
    async def choose_action(
        self,
        round_num: int,
        total_rounds_range: tuple[int, int],
        delta: Optional[float] = None,
        opponent_last_action: Optional[Action] = None,
        payoff_matrix: Optional[Dict[str, Dict[str, tuple[float, float]]]] = None
    ) -> Action:
        """复制对手上一轮动作"""
        res = "cooperate" if round_num == 1 or opponent_last_action is None else opponent_last_action
        print("=" * 20)
        print(f"[{self.name}] Round {round_num} - TFT Agent Response:")
        print(f"  {res.upper()}")
        print("=" * 20)
        return res


class LLMAgent(Agent):
    """使用 LLM 的 Agent"""
    
    def __init__(
        self,
        name: str,
        model: str,
        api_key: Optional[str] = None,
        api_base_url: str = "https://openrouter.ai/api/v1",
        temperature: float = 0.7
    ):
        """
        初始化 LLM Agent
        
        Args:
            name: Agent 名称
            model: 模型名称（如 "gpt-4", "openai/gpt-4", "google/gemini-pro"）
            api_key: API key（如果为 None，从环境变量读取）
            api_base_url: API base URL（默认使用 OpenRouter）
            temperature: 温度参数
        """
        super().__init__(name)
        self.model = model
        self.temperature = temperature
        self.api_base_url = api_base_url
        
        # 对话历史（用于多轮对话）
        self.conversation_history: List[Dict[str, str]] = []
        self.game_initialized = False
        
        # 设置日志记录器
        self.logger = setup_llm_logger(name)
        
        # 记录是否已经显示过 system prompt（用于日志优化）
        self._system_prompt_logged = False
        
        # 初始化 API 客户端
        if api_key is None:
            api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        
        if api_key:
            self.client = OpenAI(
                api_key=api_key,
                base_url=api_base_url,
            )
        else:
            self.client = None

    def signature(self) -> Dict:
        s = super().signature()
        s.update(
            {
                "model": self.model,
                "temperature": self.temperature,
                "api_base_url": self.api_base_url,
                "prompt_version": "token_only_v1",
            }
        )
        return s

    def clone(self) -> "Agent":
        # 不复用对局状态/对话历史；但复用关键配置
        cloned = LLMAgent(
            name=self.name,
            model=self.model,
            api_key=os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"),
            api_base_url=self.api_base_url,
            temperature=self.temperature,
        )
        return cloned
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """You are an agent playing an repeated trust game.

Each round, both players simultaneously choose one action:
- COOPERATE
- DEFECT

After each round, the game continues with probability δ (delta), and ends with probability (1-δ).
You know δ from the start.

Goal: maximize your expected long-run payoff (equivalently, maximize expected discounted payoff under δ).

OUTPUT REQUIREMENT:
Return exactly ONE token and nothing else:
COOPERATE
or
DEFECT"""
    
    def _build_round_message(
        self,
        round_num: int,
        total_rounds_range: tuple[int, int],
        delta: Optional[float],
        opponent_last_action: Optional[Action],
        payoff_matrix: Dict[str, Dict[str, tuple[float, float]]]
    ) -> str:
        """
        构建当前轮的消息内容
        
        Args:
            round_num: 当前回合数
            total_rounds_range: 总回合数范围
            opponent_last_action: 对手上一轮动作
            payoff_matrix: Payoff 矩阵
            
        Returns:
            当前轮的消息内容
        """
        delta_str = "unknown" if delta is None else f"{delta:.4f}"

        def _cd(seq: List[Action]) -> str:
            return " ".join("C" if a == "cooperate" else "D" for a in seq)

        if not self.game_initialized:
            message = f"""Round: {round_num}
Delta (continuation probability): {delta_str}
Your total payoff so far: {self.total_payoff:.1f}

Payoffs (You, Opponent):
- (COOPERATE, COOPERATE): {payoff_matrix['cooperate']['cooperate']}
- (COOPERATE, DEFECT): {payoff_matrix['cooperate']['defect']}
- (DEFECT, COOPERATE): {payoff_matrix['defect']['cooperate']}
- (DEFECT, DEFECT): {payoff_matrix['defect']['defect']}

Choose the action that maximizes your expected long-run payoff.
Output exactly one token: COOPERATE or DEFECT."""
        else:
            # 限制在 prompt 中展示的历史长度（避免上下文膨胀）
            k = 20
            my_hist = self.action_history[-k:]
            opp_hist = self.opponent_action_history[-k:]
            my_rate = (sum(1 for a in self.action_history if a == "cooperate") / max(1, len(self.action_history)))
            opp_rate = (sum(1 for a in self.opponent_action_history if a == "cooperate") / max(1, len(self.opponent_action_history)))

            message = f"""Round: {round_num}
Delta (continuation probability): {delta_str}
Your total payoff so far: {self.total_payoff:.1f}

Last round: You={self.action_history[-1].upper()} Opponent={self.opponent_action_history[-1].upper()} Payoff={self.payoff_history[-1]:+.1f}

Recent history (last {len(my_hist)} rounds):
You: {_cd(my_hist)}
Opp: {_cd(opp_hist)}

So far cooperation rate: You={my_rate:.2f} Opponent={opp_rate:.2f}

Choose the action that maximizes your expected long-run payoff.
Output exactly one token: COOPERATE or DEFECT."""
        
        return message
    
    def _extract_action_from_response(self, content: str) -> Optional[Action]:
        """
        从响应中提取 action（从 ##...## 标记中）
        
        Args:
            content: LLM 的响应内容
            
        Returns:
            提取的 action，如果无法提取则返回 None
        """
        # 允许两种格式：严格 token（推荐）或旧的 ##...## 包裹格式
        for pattern in (r"\b(COOPERATE|DEFECT)\b", r"##\s*(COOPERATE|DEFECT)\s*##"):
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                action_str = match.group(1).upper()
                return "cooperate" if action_str == "COOPERATE" else "defect"
        
        return None
    
    def _get_messages(self) -> List[Dict[str, str]]:
        """
        获取完整的消息列表（包括系统提示和对话历史）
        
        Returns:
            完整的消息列表
        """
        messages = [
            {"role": "system", "content": self._get_system_prompt()}
        ]
        messages.extend(self.conversation_history)
        return messages
    
    async def choose_action(
        self,
        round_num: int,
        total_rounds_range: tuple[int, int],
        delta: Optional[float] = None,
        opponent_last_action: Optional[Action] = None,
        payoff_matrix: Optional[Dict[str, Dict[str, tuple[float, float]]]] = None
    ) -> Action:
        """
        使用 LLM 选择动作（多轮对话方式）
        
        Args:
            round_num: 当前回合数
            total_rounds_range: 总回合数范围
            opponent_last_action: 对手上一轮动作
            payoff_matrix: Payoff 矩阵（如果为 None，使用默认值）
            
        Returns:
            选择的动作
        """
        # 默认 payoff 矩阵
        if payoff_matrix is None:
            payoff_matrix = {
                "cooperate": {
                    "cooperate": (2.0, 2.0),
                    "defect": (-1.0, 3.0)
                },
                "defect": {
                    "cooperate": (3.0, -1.0),
                    "defect": (0.0, 0.0)
                }
            }
        
        if self.client is None:
            # 模拟响应（用于测试/无 API key）
            return "cooperate" if self.rng.random() < 0.5 else "defect"
        
        # 构建当前轮的用户消息
        user_message = self._build_round_message(
            round_num=round_num,
            total_rounds_range=total_rounds_range,
            delta=delta,
            opponent_last_action=opponent_last_action,
            payoff_matrix=payoff_matrix,
        )
        
        # 将用户消息追加到对话历史
        self.conversation_history.append({"role": "user", "content": user_message})
        self.game_initialized = True
        
        # 获取完整的消息列表（包括系统提示和历史）
        messages = self._get_messages()
        
        # 记录发送的 prompt（优化：只在第一轮显示 system prompt）
        # self.logger.info(f"[{self.name}] Round {round_num} - Sending Prompt")
        
        if not self._system_prompt_logged:
            # 第一轮：显示 system prompt
            system_prompt = self._get_system_prompt()
            # self.logger.info(f"\n[SYSTEM PROMPT] (shown once at game start)\n{system_prompt}\n")
            # self._system_prompt_logged = True
            
            # # 显示第一轮的用户消息
            # if self.conversation_history and self.conversation_history[-1]["role"] == "user":
            #     self.logger.info(f"\n[USER MESSAGE #1]\n{self.conversation_history[-1]['content']}\n")
        else:
            # 后续轮：只显示新增的用户消息（之前的对话历史已经在之前的轮次显示过了）
            # 显示当前轮新增的用户消息
            if self.conversation_history and self.conversation_history[-1]["role"] == "user":
                self.logger.info(f"\n[USER MESSAGE #{len([m for m in self.conversation_history if m['role'] == 'user'])}]\n{self.conversation_history[-1]['content']}\n")
        
        # 重试机制：最多尝试 5 次
        max_retries = 5
        retry_delay = 2  # 每次重试前等待的秒数
        
        for attempt in range(1, max_retries + 1):
            try:
                # 尝试调用 API（注意：OpenAI 客户端为同步调用；为支持并发对局，放到线程池）
                def _call_sync():
                    return self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=self.temperature,
                    )

                response = await asyncio.to_thread(_call_sync)
                
                # 检查响应是否有效
                if not response.choices or len(response.choices) == 0:
                    raise Exception("API returned empty response")
                
                content = response.choices[0].message.content.strip()
                
                if not content:
                    raise Exception("API returned empty content")
                
                # 记录 LLM 的原始回复
                self.logger.info(f"[{self.name}] Round {round_num} - LLM Raw Response (Attempt {attempt}):")
                self.logger.info(f"  {content}")
                
                print("=" * 20)
                print(f"[{self.name}] Round {round_num} - LLM Raw Response (Attempt {attempt}):")
                print(f"  {content}")
                print("=" * 20)
                
                # 从 ##...## 标记中提取 action（在追加到历史之前先检查）
                action = self._extract_action_from_response(content)
                
                if not action:
                    # 提取 action 失败，抛出异常以便重试
                    raise Exception(f"Could not extract action from response: {content[:100]}...")
                
                # 成功提取 action，将回复追加到对话历史并返回
                self.conversation_history.append({"role": "assistant", "content": content})
                self.logger.info(f"[{self.name}] Round {round_num} - Parsed Action: {action.upper()}")
                return action
            
            except Exception as e:
                error_msg = str(e)
                
                if attempt < max_retries:
                    # 还有重试机会，记录警告并等待后重试
                    self.logger.warning(f"[{self.name}] Round {round_num} - Attempt {attempt}/{max_retries} failed: {error_msg}")
                    self.logger.info(f"[{self.name}] Round {round_num} - Waiting {retry_delay} seconds before retry...")
                    await asyncio.sleep(retry_delay)
                else:
                    # 所有尝试都失败了，记录错误并返回默认值
                    self.logger.error(f"[{self.name}] Round {round_num} - All {max_retries} attempts failed. Last error: {error_msg}")
                    return "cooperate"
        
        # 理论上不会执行到这里（因为循环会在最后一次尝试后返回），但为了安全起见
        self.logger.error(f"[{self.name}] Round {round_num} - Unexpected end of retry loop")
        return "cooperate"
