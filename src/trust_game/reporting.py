"""trust_game_code.reporting

结果汇报与绘图：
- 主实验：平均每轮得分柱形图 + 误差条（bootstrap CI）。
- 消融实验：不同 delta 下，平均得分与“性格”指标变化。
"""

from __future__ import annotations

import csv
import json
import os
from typing import Dict, List, Optional

import matplotlib.pyplot as plt


def _ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)


def save_json(obj: Dict, path: str):
    _ensure_dir(os.path.dirname(path) or ".")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def export_summary_csv(results_by_delta: List[Dict], path: str):
    """把多组 delta 的结果整理成一张 CSV（便于后处理）。"""
    _ensure_dir(os.path.dirname(path) or ".")

    fields = [
        "delta",
        "agent",
        "avg_score_per_round",
        "ci_low",
        "ci_high",
        "cooperation_rate",
        "reciprocity_rate",
        "retaliation_rate",
        "total_rounds",
        "num_games",
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for res in results_by_delta:
            delta = res.get("config", {}).get("delta")
            per_agent = res.get("per_agent", {})
            for agent_name, a in per_agent.items():
                pers = a.get("personality", {})
                w.writerow(
                    {
                        "delta": delta,
                        "agent": agent_name,
                        "avg_score_per_round": a.get("avg_score_per_round"),
                        "ci_low": a.get("avg_score_ci", {}).get("low"),
                        "ci_high": a.get("avg_score_ci", {}).get("high"),
                        "cooperation_rate": pers.get("cooperation_rate"),
                        "reciprocity_rate": pers.get("reciprocity_rate"),
                        "retaliation_rate": pers.get("retaliation_rate"),
                        "total_rounds": a.get("total_rounds"),
                        "num_games": a.get("num_games"),
                    }
                )


def plot_main_scores(result: Dict, out_path: str, title: Optional[str] = None):
    """主实验：平均得分柱形图（带误差条）。"""
    _ensure_dir(os.path.dirname(out_path) or ".")
    per_agent = result.get("per_agent", {})

    names = list(per_agent.keys())
    avgs = [per_agent[n]["avg_score_per_round"] for n in names]
    lows = [per_agent[n]["avg_score_ci"]["low"] for n in names]
    highs = [per_agent[n]["avg_score_ci"]["high"] for n in names]
    yerr = [
        [max(0.0, a - lo) for a, lo in zip(avgs, lows)],
        [max(0.0, hi - a) for a, hi in zip(avgs, highs)],
    ]

    fig = plt.figure(figsize=(max(8, len(names) * 0.8), 5))
    ax = fig.add_subplot(111)
    ax.bar(names, avgs, yerr=yerr, capsize=4)
    ax.set_ylabel("Average score per round")
    cfg = result.get("config", {})
    ax.set_title(title or f"Main experiment (delta={cfg.get('delta')}, repeats={cfg.get('repeats')}, swap={cfg.get('swap_seats')})")
    ax.tick_params(axis="x", rotation=45, labelsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_ablation(results_by_delta: List[Dict], out_dir: str):
    """消融实验：画 delta 对得分与性格指标的影响。"""
    _ensure_dir(out_dir)
    if not results_by_delta:
        return

    # delta 递增排序
    results_by_delta = sorted(results_by_delta, key=lambda r: r.get("config", {}).get("delta", 0.0))
    deltas = [r.get("config", {}).get("delta") for r in results_by_delta]
    agents = sorted(results_by_delta[0].get("per_agent", {}).keys())

    def _series(metric: str, subkey: Optional[str] = None):
        s = {a: [] for a in agents}
        for r in results_by_delta:
            pa = r.get("per_agent", {})
            for a in agents:
                if metric == "avg_score_per_round":
                    s[a].append(pa[a]["avg_score_per_round"])
                elif metric == "personality":
                    s[a].append(pa[a]["personality"].get(subkey))
                else:
                    s[a].append(None)
        return s

    # 1) 平均得分 vs delta
    fig = plt.figure(figsize=(9, 5))
    ax = fig.add_subplot(111)
    score_s = _series("avg_score_per_round")
    for a in agents:
        ax.plot(deltas, score_s[a], marker="o", label=a)
    ax.set_xlabel("delta")
    ax.set_ylabel("Average score per round")
    ax.set_title("Ablation: score vs delta")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "ablation_score_vs_delta.png"), dpi=180)
    plt.close(fig)

    # 2) 性格指标 vs delta
    for metric_name, key in [
        ("cooperation_rate", "cooperation_rate"),
        ("reciprocity_rate", "reciprocity_rate"),
        ("retaliation_rate", "retaliation_rate"),
    ]:
        fig = plt.figure(figsize=(9, 5))
        ax = fig.add_subplot(111)
        s = _series("personality", key)
        for a in agents:
            ax.plot(deltas, s[a], marker="o", label=a)
        ax.set_xlabel("delta")
        ax.set_ylabel(metric_name)
        ax.set_title(f"Ablation: {metric_name} vs delta")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, f"ablation_{metric_name}_vs_delta.png"), dpi=180)
        plt.close(fig)
