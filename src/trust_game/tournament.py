"""trust_game_code.tournament

循环 Tournament：管理多个 agent 之间的两两对战。

变更要点（对应需求）：
- 每对重复 N 次实验；每次实验做正反两局（交换座位）。
- 采用 δ-继续的回合数机制；δ 对玩家在开局已知。
- 控制随机种子以实现可复现。
- 记录每局结果，并聚合统计：平均得分 + 置信区间、合作率、互惠率、报复强度。
"""

from __future__ import annotations

import asyncio
import json
import os
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from agents import Agent, Action
from game import Game
from utils import sample_geometric_rounds, stable_int_hash


def _bootstrap_ci(
    values: List[float],
    rng: random.Random,
    n_samples: int = 2000,
    alpha: float = 0.05,
) -> Tuple[float, float]:
    """对均值做 bootstrap 置信区间（默认 95% CI）。"""
    if not values:
        return (0.0, 0.0)
    if len(values) == 1:
        return (values[0], values[0])

    m = len(values)
    means: List[float] = []
    for _ in range(n_samples):
        s = 0.0
        for _j in range(m):
            s += values[rng.randrange(m)]
        means.append(s / m)
    means.sort()
    lo_idx = int((alpha / 2) * n_samples)
    hi_idx = int((1 - alpha / 2) * n_samples) - 1
    lo = means[max(0, min(lo_idx, n_samples - 1))]
    hi = means[max(0, min(hi_idx, n_samples - 1))]
    return lo, hi


def _bootstrap_ci_weighted_mean(
    payoffs: List[float],
    rounds: List[int],
    rng: random.Random,
    n_samples: int = 2000,
    alpha: float = 0.05,
) -> Tuple[float, float]:
    """对“sum(payoff)/sum(rounds)”做 bootstrap CI。

    这是 Tournament 的主指标（平均每轮得分）的自然统计量。
    """
    if not payoffs:
        return (0.0, 0.0)
    if len(payoffs) == 1:
        denom = max(1, rounds[0])
        v = payoffs[0] / denom
        return (v, v)

    m = len(payoffs)
    stats: List[float] = []
    for _ in range(n_samples):
        s_pay = 0.0
        s_rnd = 0
        for _j in range(m):
            k = rng.randrange(m)
            s_pay += payoffs[k]
            s_rnd += rounds[k]
        stats.append(s_pay / max(1, s_rnd))
    stats.sort()
    lo_idx = int((alpha / 2) * n_samples)
    hi_idx = int((1 - alpha / 2) * n_samples) - 1
    lo = stats[max(0, min(lo_idx, n_samples - 1))]
    hi = stats[max(0, min(hi_idx, n_samples - 1))]
    return lo, hi


@dataclass
class _CountMetrics:
    """用计数聚合指标，避免“先求每局比例再平均”的加权偏差。"""
    rounds: int = 0
    coop: int = 0
    opp_coop: int = 0
    mutual_coop: int = 0
    opp_defect_prev: int = 0
    defect_after_opp_defect_prev: int = 0

    def update_from_history(self, my: List[Action], opp: List[Action]):
        t = len(my)
        self.rounds += t
        self.coop += sum(1 for a in my if a == "cooperate")
        self.opp_coop += sum(1 for a in opp if a == "cooperate")
        self.mutual_coop += sum(1 for a, b in zip(my, opp) if a == "cooperate" and b == "cooperate")
        for i in range(1, t):
            if opp[i - 1] == "defect":
                self.opp_defect_prev += 1
                if my[i] == "defect":
                    self.defect_after_opp_defect_prev += 1

    def cooperation_rate(self) -> float:
        return self.coop / self.rounds if self.rounds else 0.0

    def reciprocity_rate(self) -> Optional[float]:
        # P(You=C | Opp=C)（同一轮的联合频率条件化）
        if self.opp_coop == 0:
            return None
        return self.mutual_coop / self.opp_coop

    def retaliation_rate(self) -> Optional[float]:
        # P(You=D | Opp_{t-1}=D)
        if self.opp_defect_prev == 0:
            return None
        return self.defect_after_opp_defect_prev / self.opp_defect_prev


class Tournament:
    """循环 Tournament 管理器"""

    def __init__(
        self,
        agents: List[Agent],
        delta: float = 0.9,
        repeats: int = 10,
        swap_seats: bool = True,
        max_rounds: int = 200,
        payoff_matrix: Optional[Dict[str, Dict[str, Tuple[float, float]]]] = None,
        seed: Optional[int] = None,
        bootstrap_samples: int = 2000,
        ci_alpha: float = 0.05,
        verbose_games: bool = False,
        pair_concurrency: int = 4,
        cache_dir: str = "cache/matchups",
        use_cache: bool = True,
        overwrite_cache: bool = False,
    ):
        self.agents = agents
        self.delta = delta
        self.repeats = repeats
        self.swap_seats = swap_seats
        self.max_rounds = max_rounds
        self.payoff_matrix = payoff_matrix
        self.seed = seed
        self.bootstrap_samples = bootstrap_samples
        self.ci_alpha = ci_alpha
        self.verbose_games = verbose_games
        self.pair_concurrency = max(1, int(pair_concurrency))
        self.cache_dir = cache_dir
        self.use_cache = use_cache
        self.overwrite_cache = overwrite_cache

        # 不使用共享 RNG 推进（避免并发导致顺序依赖）；所有随机量由 stable_int_hash 派生。
        os.makedirs(self.cache_dir, exist_ok=True)

        self.game_results: List[Dict] = []
        self.per_agent: Dict[str, Dict] = {}

    def _pair_cache_key(self, a: Agent, b: Agent) -> str:
        # 将 pair 按 name 排序，保证 key 与座位无关，同时让 signature 与 name 对齐
        if a.name <= b.name:
            n1, s1 = a.name, a.signature()
            n2, s2 = b.name, b.signature()
        else:
            n1, s1 = b.name, b.signature()
            n2, s2 = a.name, a.signature()
        # 注意：seed 影响 match_seed/fixed_rounds，因此也进 key；否则会误用不同赛程
        key_int = stable_int_hash(
            [
                "pair_cache_v1",
                n1,
                json.dumps(s1, sort_keys=True, ensure_ascii=False),
                n2,
                json.dumps(s2, sort_keys=True, ensure_ascii=False),
                f"delta={self.delta}",
                f"repeats={self.repeats}",
                f"swap={self.swap_seats}",
                f"max_rounds={self.max_rounds}",
                f"seed={self.seed}",
            ]
        )
        return f"{key_int:016x}"

    def _pair_cache_path(self, a: Agent, b: Agent) -> str:
        return os.path.join(self.cache_dir, f"match_{self._pair_cache_key(a, b)}.json")

    async def _run_pair(self, a: Agent, b: Agent) -> Dict:
        """运行一对 agent 的全部对战（repeats × (1 or 2 directions)）。

        返回一个 dict，包含：
        - pair: [a.name, b.name]
        - config: 该 pair 的关键配置（用于调试）
        - game_results: 该 pair 下的逐局记录（与总输出一致的 schema）
        """
        cache_path = self._pair_cache_path(a, b)
        if self.use_cache and (not self.overwrite_cache) and os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            return cached

        pair_game_results: List[Dict] = []

        # 派生确定性的 match_seed，确保并发不改变赛程
        for r in range(1, self.repeats + 1):
            match_seed = stable_int_hash(["match_seed", self.seed, a.name, b.name, r, self.delta, self.max_rounds])
            match_rng = random.Random(match_seed)
            fixed_rounds = sample_geometric_rounds(self.delta, match_rng, self.max_rounds)

            directions = [(a, b, "A_vs_B"), (b, a, "B_vs_A")] if self.swap_seats else [(a, b, "A_vs_B")]
            for d_idx, (p1, p2, direction) in enumerate(directions):
                # 为并发安全，每局 clone 新 agent
                p1c = p1.clone()
                p2c = p2.clone()

                # 让 clone 的 RNG 也可复现（同时不依赖对局调度顺序）
                p1c.set_seed(stable_int_hash(["agent_game_seed", self.seed, match_seed, d_idx, p1.name]))
                p2c.set_seed(stable_int_hash(["agent_game_seed", self.seed, match_seed, d_idx, p2.name]))

                game_seed = stable_int_hash(["game_seed", match_seed, d_idx, p1.name, p2.name])
                game_rng = random.Random(game_seed)

                game = Game(
                    agent1=p1c,
                    agent2=p2c,
                    delta=self.delta,
                    max_rounds=self.max_rounds,
                    fixed_rounds=fixed_rounds,
                    rng=game_rng,
                    verbose=self.verbose_games,
                    rounds_range=(1, self.max_rounds),
                    payoff_matrix=self.payoff_matrix,
                )
                result = await game.play()
                pair_game_results.append(
                    {
                        "pair": [a.name, b.name],
                        "repeat": r,
                        "direction": direction,
                        "match_seed": match_seed,
                        "game_seed": game_seed,
                        "fixed_rounds": fixed_rounds,
                        "result": result,
                    }
                )

        payload = {
            "pair": [a.name, b.name],
            "config": {
                "delta": self.delta,
                "repeats": self.repeats,
                "swap_seats": self.swap_seats,
                "max_rounds": self.max_rounds,
                "seed": self.seed,
                "agent_signatures": {
                    a.name: a.signature(),
                    b.name: b.signature(),
                },
            },
            "game_results": pair_game_results,
        }

        if self.use_cache:
            tmp = cache_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp, cache_path)

        return payload

    async def run(self) -> Dict:
        if not (0.0 <= self.delta < 1.0):
            raise ValueError(f"delta must be in [0, 1). Got: {self.delta}")
        if self.repeats < 1:
            raise ValueError(f"repeats must be >= 1. Got: {self.repeats}")

        # 初始化统计
        scores: Dict[str, float] = {a.name: 0.0 for a in self.agents}
        total_rounds: Dict[str, int] = {a.name: 0 for a in self.agents}
        per_game_avg: Dict[str, List[float]] = {a.name: [] for a in self.agents}
        per_game_payoff: Dict[str, List[float]] = {a.name: [] for a in self.agents}
        per_game_rounds: Dict[str, List[int]] = {a.name: [] for a in self.agents}
        count_metrics: Dict[str, _CountMetrics] = {a.name: _CountMetrics() for a in self.agents}

        self.game_results = []

        # 两两对战（以“pair”为并发粒度）
        sem = asyncio.Semaphore(self.pair_concurrency)

        async def _run_pair_guarded(a: Agent, b: Agent) -> Dict:
            async with sem:
                return await self._run_pair(a, b)

        tasks: List[asyncio.Task] = []
        for i in range(len(self.agents)):
            for j in range(i + 1, len(self.agents)):
                tasks.append(asyncio.create_task(_run_pair_guarded(self.agents[i], self.agents[j])))

        for fut in asyncio.as_completed(tasks):
            pair_payload = await fut
            pair_games = pair_payload.get("game_results", [])
            # 将 pair 的逐局结果合并到总输出，并更新统计
            for g in pair_games:
                result = g["result"]

                scores[result["agent1_name"]] += result["agent1_total_payoff"]
                scores[result["agent2_name"]] += result["agent2_total_payoff"]
                total_rounds[result["agent1_name"]] += result["total_rounds"]
                total_rounds[result["agent2_name"]] += result["total_rounds"]

                p1_avg = result["agent1_total_payoff"] / max(1, result["total_rounds"])
                p2_avg = result["agent2_total_payoff"] / max(1, result["total_rounds"])
                per_game_avg[result["agent1_name"]].append(p1_avg)
                per_game_avg[result["agent2_name"]].append(p2_avg)

                per_game_payoff[result["agent1_name"]].append(result["agent1_total_payoff"])
                per_game_payoff[result["agent2_name"]].append(result["agent2_total_payoff"])
                per_game_rounds[result["agent1_name"]].append(result["total_rounds"])
                per_game_rounds[result["agent2_name"]].append(result["total_rounds"])

                # 从 result['history'] 计算“性格”指标，不依赖 agent 对象（便于缓存）
                hist = result.get("history", [])
                my1: List[Action] = [h["agent1_action"] for h in hist]
                my2: List[Action] = [h["agent2_action"] for h in hist]
                count_metrics[result["agent1_name"]].update_from_history(my1, my2)
                count_metrics[result["agent2_name"]].update_from_history(my2, my1)

                self.game_results.append(g)

        # 汇总：平均每轮得分
        avg_scores: Dict[str, float] = {}
        ci: Dict[str, Tuple[float, float]] = {}
        ci_rng = random.Random(stable_int_hash(["ci_rng", self.seed, self.delta]))

        for name in scores.keys():
            if total_rounds[name] > 0:
                avg_scores[name] = scores[name] / total_rounds[name]
            else:
                avg_scores[name] = 0.0
            ci[name] = _bootstrap_ci_weighted_mean(
                per_game_payoff[name],
                per_game_rounds[name],
                ci_rng,
                self.bootstrap_samples,
                self.ci_alpha,
            )

        rankings = sorted(avg_scores.items(), key=lambda x: x[1], reverse=True)

        # 输出 per_agent 结构
        self.per_agent = {}
        for name in scores.keys():
            cm = count_metrics[name]
            self.per_agent[name] = {
                "total_score": scores[name],
                "total_rounds": total_rounds[name],
                "avg_score_per_round": avg_scores[name],
                "avg_score_ci": {"low": ci[name][0], "high": ci[name][1], "alpha": self.ci_alpha},
                "num_games": len(per_game_avg[name]),
                "personality": {
                    "cooperation_rate": cm.cooperation_rate(),
                    "reciprocity_rate": cm.reciprocity_rate(),
                    "retaliation_rate": cm.retaliation_rate(),
                    "counts": {
                        "rounds": cm.rounds,
                        "coop": cm.coop,
                        "opp_coop": cm.opp_coop,
                        "mutual_coop": cm.mutual_coop,
                        "opp_defect_prev": cm.opp_defect_prev,
                        "defect_after_opp_defect_prev": cm.defect_after_opp_defect_prev,
                    },
                },
                "per_game_avg_score": per_game_avg[name],
            }

        return {
            "config": {
                "delta": self.delta,
                "repeats": self.repeats,
                "swap_seats": self.swap_seats,
                "max_rounds": self.max_rounds,
                "seed": self.seed,
                "bootstrap_samples": self.bootstrap_samples,
                "ci_alpha": self.ci_alpha,
            },
            "agents": [a.name for a in self.agents],
            "per_agent": self.per_agent,
            "rankings": rankings,
            "game_results": self.game_results,
            "total_games": len(self.game_results),
        }

    def print_summary(self, result: Dict):
        print("\n" + "=" * 80)
        print("Tournament Summary")
        print("=" * 80)
        cfg = result.get("config", {})
        print(f"delta: {cfg.get('delta')} | repeats: {cfg.get('repeats')} | swap_seats: {cfg.get('swap_seats')} | max_rounds: {cfg.get('max_rounds')} | seed: {cfg.get('seed')}")
        print(f"Total Games: {result.get('total_games')}\n")

        print("Rankings (by Average Score per Round):")
        print("-" * 80)
        print(f"{'Rank':<6} {'Agent Name':<25} {'Avg Score/Round':<18} {'CI (low, high)':<22} {'Rounds':<10}")
        print("-" * 80)
        for rank, (name, avg_score) in enumerate(result.get("rankings", []), start=1):
            pa = result["per_agent"][name]
            ci = pa["avg_score_ci"]
            rounds = pa["total_rounds"]
            print(f"{rank:<6} {name:<25} {avg_score:<18.4f} ({ci['low']:.4f}, {ci['high']:.4f}) {rounds:<10}")
        print("=" * 80 + "\n")