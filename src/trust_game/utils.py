"""trust_game_code.utils

小工具函数：随机种子、稳定哈希、以及几何(δ-继续)回合数采样。
"""

from __future__ import annotations

import hashlib
import random
from typing import Iterable, Optional


def stable_int_hash(parts: Iterable[object]) -> int:
    """稳定的 64-bit 整数哈希（跨进程/跨平台稳定）。"""
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8"))
        h.update(b"|")
    # 取前 8 字节作为 64-bit 整数
    return int.from_bytes(h.digest()[:8], "big", signed=False)


def seed_everything(seed: int):
    """尽量对全局随机源做初始化（主要用于第三方库可能用到的 random）。"""
    random.seed(seed)


def sample_geometric_rounds(delta: float, rng: random.Random, max_rounds: int) -> int:
    """按 δ-继续机制采样一局的回合数。

    机制：至少进行 1 轮；每轮结束后，以概率 δ 继续下一轮，以 1-δ 结束。
    为避免极端情况，使用 max_rounds 做硬上限。
    """
    if not (0.0 <= delta < 1.0):
        raise ValueError(f"delta must be in [0, 1). Got: {delta}")
    if max_rounds < 1:
        raise ValueError(f"max_rounds must be >= 1. Got: {max_rounds}")

    rounds = 1
    while rounds < max_rounds and rng.random() < delta:
        rounds += 1
    return rounds
