"""trust_game_code.main

主入口：命令行接口。

支持：
- 单局对战（single）
- 单个 delta 的 tournament（tournament）
- 多个 delta 的消融实验（ablation）
"""
import asyncio
import json
import argparse
import os
import random
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

from agents import Agent, RandomAgent, GrimTriggerAgent, TFTAgent, LLMAgent
from game import Game
from tournament import Tournament
from reporting import export_summary_csv, plot_ablation, plot_main_scores, save_json
from utils import seed_everything, stable_int_hash


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Repeated Prisoner's Dilemma (Trust Game) Benchmark"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["single", "tournament", "ablation"],
        default="tournament",
        help="运行模式：single（单局游戏）或 tournament（循环 tournament）"
    )
    parser.add_argument(
        "--agents",
        type=str,
        nargs="+",
        help="Agent 列表，格式：'name:type:model' 或 'name:type'。"
             "type 可以是 'random', 'tft' (TFT), 'grim' (Grim Trigger), 'llm'。"
             "对于 llm，需要指定 model（如 'gpt-4'）"
    )
    # 兼容旧参数：rounds-range 在 δ-继续机制下不再使用（保留仅为向后兼容）
    parser.add_argument(
        "--rounds-range",
        type=int,
        nargs=2,
        default=[3, 7],
        metavar=("MIN", "MAX"),
        help="[兼容参数] 固定回合数范围（δ 机制下不再使用；仅保留不破坏旧脚本）"
    )

    parser.add_argument("--delta", type=float, default=0.9, help="δ：每轮继续的概率（0<=δ<1）。")
    parser.add_argument(
        "--deltas",
        type=float,
        nargs="+",
        default=[0.85, 0.9, 0.95],
        help="消融实验用的 δ 列表（建议 <=0.95，使期望回合数 <=20）。",
    )
    parser.add_argument("--max-rounds", type=int, default=25, help="单局最大回合数硬上限（防止极端长局）。")

    parser.add_argument(
        "--repeats",
        type=int,
        default=None,
        help="每对 agent 重复实验次数（每次默认做正反两局）。",
    )
    parser.add_argument(
        "--num-games",
        type=int,
        default=1,
        help="[兼容参数] 等价于 --repeats（将来可能移除）。",
    )
    parser.add_argument("--no-swap-seats", action="store_true", help="关闭正反两局（不交换座位）。")

    parser.add_argument("--seed", type=int, default=1234, help="随机种子（用于可复现实验）。")
    parser.add_argument("--pair-concurrency", type=int, default=4, help="并发对战的 pair 数（每个 pair 表示一对 agent 在打）。")
    parser.add_argument("--cache-dir", type=str, default="cache/matchups", help="对战缓存目录（按 pair 保存）。")
    parser.add_argument("--no-cache", action="store_true", help="关闭缓存读取/写入（强制每次都重跑）。")
    parser.add_argument("--overwrite-cache", action="store_true", help="重新生成并覆盖已存在的 pair 缓存。")
    parser.add_argument("--bootstrap-samples", type=int, default=2000, help="bootstrap 抽样次数（用于 CI）。")
    parser.add_argument("--ci-alpha", type=float, default=0.05, help="置信区间显著性水平 alpha（默认 0.05 -> 95% CI）。")
    parser.add_argument("--plot-dir", type=str, default="plots", help="绘图输出目录。")
    parser.add_argument(
        "--output",
        type=str,
        help="结果输出文件路径（JSON 格式）"
    )
    
    args = parser.parse_args()

    # 全局随机源初始化（第三方库可能使用）
    seed_everything(args.seed)

    def _warn_delta_cost(d: float):
        if 0 <= d < 1:
            exp_rnds = 1.0 / max(1e-12, (1.0 - d))
            if exp_rnds > 20.0:
                print(f"⚠ Warning: delta={d} implies E[T]≈{exp_rnds:.1f} rounds (>20). Cost may be high.")

    if args.mode in {"single", "tournament"}:
        _warn_delta_cost(args.delta)
    elif args.mode == "ablation":
        for d in args.deltas:
            _warn_delta_cost(d)
    
    # 解析 agents
    agents: List[Agent] = []
    
    if args.agents:
        # 从命令行参数解析
        for agent_spec in args.agents:
            parts = agent_spec.split(":")
            if len(parts) < 2:
                print(f"⚠ Warning: Invalid agent spec '{agent_spec}', skipping")
                continue
            
            name = parts[0]
            agent_type = parts[1].lower()
            
            if agent_type == "random":
                cooperate_prob = float(parts[2]) if len(parts) > 2 else 0.5
                agents.append(RandomAgent(name, cooperate_prob))
            elif agent_type == "tft":
                agents.append(TFTAgent(name))
            elif agent_type == "grim":
                agents.append(GrimTriggerAgent(name))
            elif agent_type == "llm":
                if len(parts) < 3:
                    print(f"⚠ Warning: LLM agent '{name}' requires model name, skipping")
                    continue
                model = parts[2]
                agents.append(LLMAgent(name, model))
            else:
                print(f"⚠ Warning: Unknown agent type '{agent_type}', skipping")
    else:
        # 使用默认 agents（baseline）
        agents = [
            RandomAgent("Random-1", cooperate_prob=0.5),
            RandomAgent("Random-2", cooperate_prob=0.7),
            GrimTriggerAgent("Grim Trigger-1"),
            GrimTriggerAgent("Grim Trigger-2")
        ]
    
    if not agents:
        print("❌ Error: No valid agents specified")
        return

    # 给 agent 分配稳定随机种子（Tournament 里也会再次设置，保证一致）
    for idx, a in enumerate(agents):
        a.set_seed(stable_int_hash(["agent_seed", args.seed, idx, a.name]))

    # 为 agents 设置稳定 RNG 种子（单局模式也可复现）
    for idx, a in enumerate(agents):
        a.set_seed(stable_int_hash(["agent_seed", args.seed, idx, a.name]))
    
    repeats = args.repeats if args.repeats is not None else args.num_games
    swap_seats = not args.no_swap_seats

    print(f"\nAgents: {[a.name for a in agents]}")
    print(f"Mode: {args.mode}")
    print(f"delta: {args.delta} | max_rounds: {args.max_rounds} | repeats: {repeats} | swap_seats: {swap_seats} | seed: {args.seed}")
    print(f"pair_concurrency: {args.pair_concurrency} | cache_dir: {args.cache_dir} | cache: {not args.no_cache} | overwrite_cache: {args.overwrite_cache}\n")
    
    # 运行游戏
    if args.mode == "single":
        if len(agents) < 2:
            print("❌ Error: Single game mode requires at least 2 agents")
            return
        
        game = Game(
            agent1=agents[0],
            agent2=agents[1],
            delta=args.delta,
            max_rounds=args.max_rounds,
            rng=random.Random(stable_int_hash(["single_game", args.seed, agents[0].name, agents[1].name, args.delta])),
            verbose=True,
            rounds_range=(1, args.max_rounds),
        )
        result = await game.play()
        
        # 打印结果
        print(f"\nGame Result:")
        print(f"  Agent 1: {result['agent1_name']}")
        print(f"  Agent 2: {result['agent2_name']}")
        print(f"  Total Rounds: {result['total_rounds']}")
        print(f"  Agent 1 Total Payoff: {result['agent1_total_payoff']:.2f}")
        print(f"  Agent 2 Total Payoff: {result['agent2_total_payoff']:.2f}")
        
        print("\nRound History:")
        print("-" * 60)
        for round_data in result['history']:
            print(f"Round {round_data['round']}: "
                  f"{result['agent1_name']} {round_data['agent1_action'].upper()}, "
                  f"{result['agent2_name']} {round_data['agent2_action'].upper()} | "
                  f"Payoffs: {round_data['agent1_payoff']:.1f} / {round_data['agent2_payoff']:.1f}")
        
        # 保存结果
        if args.output:
            save_json(result, args.output)
            print(f"\n✓ Result saved to {args.output}")
    
    elif args.mode == "tournament":
        tournament = Tournament(
            agents=agents,
            delta=args.delta,
            repeats=repeats,
            swap_seats=swap_seats,
            max_rounds=args.max_rounds,
            seed=args.seed,
            bootstrap_samples=args.bootstrap_samples,
            ci_alpha=args.ci_alpha,
            pair_concurrency=args.pair_concurrency,
            cache_dir=args.cache_dir,
            use_cache=(not args.no_cache),
            overwrite_cache=args.overwrite_cache,
        )
        result = await tournament.run()
        tournament.print_summary(result)

        # 保存结果
        if args.output:
            save_json(result, args.output)
            print(f"\n✓ Result saved to {args.output}")

        # 主实验绘图
        plot_path = os.path.join(args.plot_dir, f"main_score_bar_delta_{args.delta:.3f}.png")
        plot_main_scores(result, plot_path)
        print(f"✓ Plot saved to {plot_path}")

    else:  # ablation
        results_by_delta: List[Dict] = []
        os.makedirs(args.plot_dir, exist_ok=True)
        out_dir = os.path.dirname(args.output) if args.output else "results"
        os.makedirs(out_dir, exist_ok=True)

        for d in args.deltas:
            t = Tournament(
                agents=agents,
                delta=d,
                repeats=repeats,
                swap_seats=swap_seats,
                max_rounds=args.max_rounds,
                seed=args.seed,
                bootstrap_samples=args.bootstrap_samples,
                ci_alpha=args.ci_alpha,
                pair_concurrency=args.pair_concurrency,
                cache_dir=args.cache_dir,
                use_cache=(not args.no_cache),
                overwrite_cache=args.overwrite_cache,
            )
            res = await t.run()
            results_by_delta.append(res)

            # 每个 delta 单独保存
            per_path = os.path.join(out_dir, f"tournament_delta_{d:.3f}.json")
            save_json(res, per_path)
            plot_main_scores(res, os.path.join(args.plot_dir, f"score_bar_delta_{d:.3f}.png"), title=f"delta={d:.3f}")

        # 汇总输出
        plot_ablation(results_by_delta, args.plot_dir)
        export_summary_csv(results_by_delta, os.path.join(out_dir, "ablation_summary.csv"))
        summary = {"results": results_by_delta}
        if args.output:
            save_json(summary, args.output)
            print(f"\n✓ Ablation summary saved to {args.output}")
        else:
            save_json(summary, os.path.join(out_dir, "ablation_summary.json"))


if __name__ == "__main__":
    asyncio.run(main())

