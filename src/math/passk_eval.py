import argparse
import json
import math
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from tqdm import tqdm
except Exception:
    def tqdm(iterable, desc=None):
        return iterable

try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv():
        return None


load_dotenv()


def extract_after_marker(s: str, marker: str) -> str:
    if not s:
        return ""
    idx = s.find(marker)
    if idx == -1:
        return s.strip()
    return s[idx + len(marker):].strip()


def normalize_answer(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", "", s.strip())


def parse_binary_judgement(text: str) -> int:
    t = (text or "").strip()
    if not t:
        return 0
    first = t.split()[0][:1]
    return 1 if first == "1" else 0


def estimate_tokens(text: str) -> int:
    """Best-effort token estimator when provider usage is unavailable."""
    if not text:
        return 0
    t = text.strip()
    if not t:
        return 0
    return max(1, math.ceil(len(t) / 4))


def maybe_usage_total(usage_obj) -> Optional[int]:
    if usage_obj is None:
        return None
    total = getattr(usage_obj, "total_tokens", None)
    if isinstance(total, int):
        return total
    if isinstance(usage_obj, dict):
        v = usage_obj.get("total_tokens")
        if isinstance(v, int):
            return v
    return None


def parse_model_id_from_filename(path: str, method: str) -> Optional[str]:
    stem = Path(path).stem
    if method == "naive":
        m = re.search(r"__openrouter__([^_].*?)__judge=", stem)
    else:
        m = re.search(r"__turtle__openrouter__([^_].*?)__judge=", stem)
    if not m:
        return None
    token = m.group(1)
    if "_" in token:
        provider, rest = token.split("_", 1)
        return f"{provider}/{rest}"
    return token


def safe_model_id(model_id: str) -> str:
    return model_id.replace("/", "_")


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def collect_result_files(results_dir: str, dataset_name: str) -> Tuple[List[str], List[str]]:
    root = Path(results_dir)
    naive = sorted(
        str(p) for p in root.glob(f"{dataset_name}__openrouter__*__judge=*.json") if "__turtle__" not in p.name and "__passk__" not in p.name
    )
    turtle = sorted(
        str(p) for p in root.glob(f"{dataset_name}__turtle__openrouter__*__judge=*.json") if "__passk__" not in p.name
    )
    return naive, turtle


def judge_system_prompt() -> str:
    return (
        "You are a strict grader.\n"
        "Analyze and compare the extracted model answer with the expected answer for equivalence. "
        "Then on a new line output exactly $$$$\n"
        "and after $$$$ output ONLY 1 if equivalent else 0."
    )


def judge_user_prompt(problem: str, exp_ans: str, model_ans: str) -> str:
    return (
        f"Problem:\n{problem}\n\n"
        f"Expected answer:\n{exp_ans}\n\n"
        f"Model answer:\n{model_ans}\n\n"
        "Now analyze and compare the answers. After that output $$$$ and give your 0/1 judgement result."
    )


def player_system_prompt() -> str:
    return (
        "You are a math solver. You should answer the question by reasoning.\n"
        "At the end of your reasoning, output the final answer on a new line that starts with exactly ####\n"
        "After ####, output ONLY the final answer (no extra words)."
    )


def estimate_naive_tokens_from_record(r: Dict) -> Optional[int]:
    gen_ans = r.get("gen_ans", "")
    # 只统计 player 输出，不包含任何输入 token，不包含 judge token
    return estimate_tokens(gen_ans)


def estimate_turtle_tokens_from_record(r: Dict) -> Optional[int]:
    history = r.get("turtle_history") or []
    # 只统计 player 每轮输出，不包含 judge 输出与任意输入 token
    if isinstance(history, list) and history:
        total = 0
        for h in history:
            if not isinstance(h, dict):
                continue
            total += estimate_tokens(h.get("player_raw", ""))
        return total

    # 兜底：无 history 时仅用最终输出
    return estimate_tokens(r.get("gen_ans", ""))


def map_records_by_problem(records: List[Dict]) -> Dict[str, Dict]:
    out = {}
    for r in records:
        if not isinstance(r, dict):
            continue
        p = r.get("problem", "")
        if not p:
            continue
        if p not in out:
            out[p] = r
    return out


def compute_average_tokens(naive_files: List[str], turtle_files: List[str]) -> Dict:
    naive_all = []
    turtle_all = []
    by_file = {"paired_by_model": {}}

    naive_by_model = {}
    turtle_by_model = {}
    for p in naive_files:
        mid = parse_model_id_from_filename(p, "naive")
        if mid:
            naive_by_model[mid] = p
    for p in turtle_files:
        mid = parse_model_id_from_filename(p, "turtle")
        if mid:
            turtle_by_model[mid] = p

    common_models = sorted(set(naive_by_model.keys()) & set(turtle_by_model.keys()))
    for model_id in common_models:
        naive_path = naive_by_model[model_id]
        turtle_path = turtle_by_model[model_id]

        naive_map = map_records_by_problem(load_json(naive_path))
        turtle_map = map_records_by_problem(load_json(turtle_path))
        overlap = sorted(set(naive_map.keys()) & set(turtle_map.keys()))

        naive_vals = []
        turtle_vals = []
        for p in overlap:
            vn = estimate_naive_tokens_from_record(naive_map[p])
            vt = estimate_turtle_tokens_from_record(turtle_map[p])
            if isinstance(vn, int) and vn >= 0 and isinstance(vt, int) and vt >= 0:
                naive_vals.append(vn)
                turtle_vals.append(vt)
                naive_all.append(vn)
                turtle_all.append(vt)

        by_file["paired_by_model"][model_id] = {
            "naive_file": Path(naive_path).name,
            "turtle_file": Path(turtle_path).name,
            "naive_n_all": len(naive_map),
            "turtle_n_all": len(turtle_map),
            "overlap_n": len(overlap),
            "used_n": len(naive_vals),
            "naive_avg_tokens_on_overlap": (sum(naive_vals) / len(naive_vals)) if naive_vals else None,
            "turtle_avg_tokens_on_overlap": (sum(turtle_vals) / len(turtle_vals)) if turtle_vals else None,
        }

    naive_avg = (sum(naive_all) / len(naive_all)) if naive_all else 0.0
    turtle_avg = (sum(turtle_all) / len(turtle_all)) if turtle_all else 0.0
    ratio = (turtle_avg / naive_avg) if naive_avg > 0 else 1.0
    k_global = max(1, int(round(ratio)))

    k_by_model = {}
    for model_id, d in by_file["paired_by_model"].items():
        n_avg = d.get("naive_avg_tokens_on_overlap")
        t_avg = d.get("turtle_avg_tokens_on_overlap")
        if isinstance(n_avg, (int, float)) and isinstance(t_avg, (int, float)) and float(n_avg) > 0:
            r = float(t_avg) / float(n_avg)
            k_m = max(1, int(round(r)))
            k_by_model[model_id] = {
                "k": int(k_m),
                "ratio_turtle_over_naive": float(r),
                "naive_avg_tokens_on_overlap": float(n_avg),
                "turtle_avg_tokens_on_overlap": float(t_avg),
                "overlap_n": int(d.get("overlap_n") or 0),
                "used_n": int(d.get("used_n") or 0),
            }
        else:
            k_by_model[model_id] = {
                "k": 1,
                "ratio_turtle_over_naive": None,
                "naive_avg_tokens_on_overlap": n_avg,
                "turtle_avg_tokens_on_overlap": t_avg,
                "overlap_n": int(d.get("overlap_n") or 0),
                "used_n": int(d.get("used_n") or 0),
            }
    return {
        "naive_avg_tokens": naive_avg,
        "turtle_avg_tokens": turtle_avg,
        "ratio_turtle_over_naive": ratio,
        "k_global": k_global,
        "k_metric": "player_output_tokens_only",
        "k_by_model": k_by_model,
        "details": by_file,
    }


class OpenRouterRunner:
    """
    精简后的调用器：复用 naive.py 的 LLMClient（OpenAI client），不传 max_tokens。
    """

    def __init__(self, llm, verbose_calls: bool = False):
        self.llm = llm
        self.verbose_calls = bool(verbose_calls)

    def chat_with_retry(
        self,
        model: str,
        messages: List[Dict],
        temperature: float,
        max_attempts: int,
        call_tag: str = "",
    ) -> Tuple[str, int]:
        last_err = None
        for attempt in range(1, int(max_attempts) + 1):
            t0 = time.time()
            if self.verbose_calls:
                print(f"[CALL] tag={call_tag or '-'} model={model} attempt={attempt}/{max_attempts}")
            try:
                # 不在 API 请求里传 max_tokens（按你的要求）
                text = (self.llm.chat(model, messages, temperature=temperature) or "").strip()
                if text:
                    if self.verbose_calls:
                        dt = time.time() - t0
                        print(
                            f"[CALL_OK] tag={call_tag or '-'} model={model} "
                            f"elapsed={dt:.2f}s resp_chars={len(text)}"
                        )
                    # usage 暂用输出 token 估算；k 的统计不依赖这个字段
                    return text, estimate_tokens(text)
                last_err = RuntimeError("empty_response")
            except Exception as e:
                last_err = e
                if self.verbose_calls:
                    dt = time.time() - t0
                    print(
                        f"[CALL_ERR] tag={call_tag or '-'} model={model} "
                        f"elapsed={dt:.2f}s err={last_err}"
                    )
            if attempt < int(max_attempts):
                time.sleep(min(10, attempt * 2))
        raise RuntimeError(f"chat_with_retry exhausted; err={last_err}")


def make_passk_out_path(results_dir: str, dataset_name: str, player_model: str, judge_model: str) -> str:
    return os.path.join(
        results_dir,
        f"{dataset_name}__passk__openrouter__{safe_model_id(player_model)}__judge={safe_model_id(judge_model)}.json",
    )


def evaluate_passk_for_model(
    runner: OpenRouterRunner,
    model_id: str,
    judge_model: str,
    source_rows: List[Dict],
    out_path: str,
    k: int,
    temperature: float,
    max_attempts: int,
    max_n: int,
    verbose_progress: bool,
) -> Dict:
    prev: List[Dict] = []
    done = set()
    if os.path.exists(out_path):
        try:
            prev_obj = load_json(out_path)
            if isinstance(prev_obj, list):
                prev = prev_obj
                for r in prev:
                    p = (r or {}).get("problem", "")
                    if p and isinstance(r.get("attempts"), list) and len(r["attempts"]) >= k:
                        done.add(p)
        except Exception:
            pass

    rows = source_rows[:max_n] if max_n > 0 else source_rows
    out = list(prev)
    processed = set(done)

    total_rows = len(rows)
    pbar = tqdm(rows, desc=f"pass@k {model_id}")
    for row_idx, row in enumerate(pbar, start=1):
        problem = row.get("problem", "")
        if not problem or problem in processed:
            continue
        if verbose_progress:
            print(
                f"[ROW] model={model_id} row={row_idx}/{total_rows} "
                f"problem_len={len(problem)} out_path={Path(out_path).name}"
            )
        exp_ans = row.get("exp_ans", "") or row.get("final_answer", "")
        solution = row.get("solution", "")

        attempts = []
        pass_correct = 0
        token_total = 0

        for i in range(1, k + 1):
            player_msgs = [
                {"role": "system", "content": player_system_prompt()},
                {"role": "user", "content": problem},
            ]
            try:
                gen_ans, player_tokens = runner.chat_with_retry(
                    model=model_id,
                    messages=player_msgs,
                    temperature=temperature,
                    max_attempts=max_attempts,
                    call_tag=f"{model_id} row={row_idx}/{total_rows} attempt={i}/{k} role=player",
                )
            except Exception as e:
                if verbose_progress:
                    print(
                        f"[ATTEMPT_FAIL] model={model_id} row={row_idx}/{total_rows} "
                        f"attempt={i}/{k} role=player err={e}"
                    )
                attempts.append({
                    "idx": i,
                    "gen_ans": "",
                    "extracted_gen_ans": "",
                    "judge_raw": f"PLAYER_API_ERROR: {e}",
                    "extracted_judgement": "0",
                    "correct": 0,
                    "status": "player_api_error",
                    "token_usage": {
                        "player_total_tokens": 0,
                        "judge_total_tokens": 0,
                        "total_tokens": 0,
                    },
                })
                continue

            extracted_gen_ans = extract_after_marker(gen_ans, "####")
            correct = 0
            status = "format_error_empty_extracted_answer"
            judge_raw = "SKIPPED_EMPTY_EXTRACTED_ANSWER"
            judge_tokens = 0

            if normalize_answer(extracted_gen_ans):
                judge_msgs = [
                    {"role": "system", "content": judge_system_prompt()},
                    {"role": "user", "content": judge_user_prompt(problem, exp_ans, extracted_gen_ans)},
                ]
                try:
                    judge_raw, judge_tokens = runner.chat_with_retry(
                        model=judge_model,
                        messages=judge_msgs,
                        temperature=0.0,
                        max_attempts=max_attempts,
                        call_tag=f"{model_id} row={row_idx}/{total_rows} attempt={i}/{k} role=judge",
                    )
                    extracted_judgement = extract_after_marker(judge_raw, "$$$$")
                    correct = parse_binary_judgement(extracted_judgement)
                    status = "ok" if judge_raw.strip() else "judge_failed"
                except Exception as e:
                    judge_raw = f"JUDGE_API_ERROR: {e}"
                    extracted_judgement = "0"
                    correct = 0
                    status = "judge_api_error"
                    if verbose_progress:
                        print(
                            f"[ATTEMPT_FAIL] model={model_id} row={row_idx}/{total_rows} "
                            f"attempt={i}/{k} role=judge err={e}"
                        )
            else:
                extracted_judgement = "0"

            attempt_obj = {
                "idx": i,
                "gen_ans": gen_ans,
                "extracted_gen_ans": extracted_gen_ans,
                "judge_raw": judge_raw,
                "extracted_judgement": extracted_judgement,
                "correct": int(correct),
                "status": status,
                "token_usage": {
                    "player_total_tokens": int(player_tokens),
                    "judge_total_tokens": int(judge_tokens),
                    "total_tokens": int(player_tokens + judge_tokens),
                },
            }
            attempts.append(attempt_obj)
            token_total += int(player_tokens + judge_tokens)
            if correct == 1:
                pass_correct = 1
            if verbose_progress:
                print(
                    f"[ATTEMPT] model={model_id} row={row_idx}/{total_rows} attempt={i}/{k} "
                    f"status={status} correct={correct} tokens={player_tokens + judge_tokens}"
                )

        out.append({
            "problem": problem,
            "solution": solution,
            "exp_ans": exp_ans,
            "pass_k_correct": int(pass_correct),
            "k": int(k),
            "temperature": float(temperature),
            "attempts": attempts,
            "token_usage": {
                "total_tokens_all_attempts": int(token_total),
                "avg_tokens_per_attempt": (token_total / k) if k > 0 else 0,
            },
            "meta": {
                "method": "passk",
                "provider": "openrouter",
                "player_model": model_id,
                "judge_model": judge_model,
                "ts": time.time(),
            },
        })
        processed.add(problem)
        save_json(out_path, out)
        if verbose_progress:
            print(
                f"[ROW_DONE] model={model_id} row={row_idx}/{total_rows} "
                f"pass_k_correct={pass_correct} saved={Path(out_path).name}"
            )

    total = len(out)
    ok = sum(1 for r in out if int(r.get("pass_k_correct", 0)) == 1)
    return {
        "model_id": model_id,
        "out_path": out_path,
        "n_total": total,
        "n_correct": ok,
        "accuracy": (ok / total) if total > 0 else 0.0,
    }


def build_source_rows_for_model(naive_path: str, turtle_path: Optional[str]) -> List[Dict]:
    naive = load_json(naive_path)
    if not turtle_path or not os.path.exists(turtle_path):
        return [r for r in naive if isinstance(r, dict) and r.get("problem")]

    turtle = load_json(turtle_path)
    turtle_set = {r.get("problem", "") for r in turtle if isinstance(r, dict)}
    rows = []
    for r in naive:
        if not isinstance(r, dict):
            continue
        p = r.get("problem", "")
        if p and p in turtle_set:
            rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results_dir", default="results")
    ap.add_argument("--dataset_name", default="hle")
    ap.add_argument("--judge_model", default="x-ai/grok-4.1-fast")
    ap.add_argument("--openrouter_base_url", default="https://openrouter.ai/api/v1")
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--max_attempts", type=int, default=3)
    ap.add_argument("--max_n", type=int, default=-1)
    ap.add_argument("--k_override", type=int, default=-1)
    ap.add_argument("--compute_k_only", action="store_true", default=False)
    ap.add_argument("--verbose_calls", action="store_true", default=False)
    ap.add_argument("--verbose_progress", action="store_true", default=False)
    ap.add_argument("--player_model", default="")
    args = ap.parse_args()

    naive_files, turtle_files = collect_result_files(args.results_dir, args.dataset_name)
    if not naive_files or not turtle_files:
        raise RuntimeError("Cannot find naive/turtle files to compute k.")

    stats = compute_average_tokens(naive_files, turtle_files)
    if args.k_override > 0:
        # 覆盖：如果指定 --player_model，则只覆盖该模型的 k；否则覆盖全部模型
        if args.player_model:
            if args.player_model not in stats.get("k_by_model", {}):
                stats.setdefault("k_by_model", {})[args.player_model] = {"k": int(args.k_override)}
            stats["k_by_model"][args.player_model]["k"] = int(args.k_override)
        else:
            for m in list(stats.get("k_by_model", {}).keys()):
                stats["k_by_model"][m]["k"] = int(args.k_override)
            stats["k_global"] = int(args.k_override)

    stats_path = os.path.join(args.results_dir, f"{args.dataset_name}__passk_k_stats.json")
    save_json(stats_path, stats)
    print(
        f"[INFO] naive_avg_tokens={stats['naive_avg_tokens']:.2f}, "
        f"turtle_avg_tokens={stats['turtle_avg_tokens']:.2f}, "
        f"ratio={stats['ratio_turtle_over_naive']:.3f}, k_global={stats['k_global']}"
    )
    print(f"[INFO] k stats saved: {stats_path}")

    if args.compute_k_only:
        return

    # 复用 naive.py 的 OpenAI client（不传 max_tokens）
    from filter import LLMClient
    llm = LLMClient(
        provider="openrouter",
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY"),
        openrouter_base_url=args.openrouter_base_url,
    )
    runner = OpenRouterRunner(llm=llm, verbose_calls=args.verbose_calls)
    turtle_map = {
        parse_model_id_from_filename(p, "turtle"): p
        for p in turtle_files
        if parse_model_id_from_filename(p, "turtle")
    }

    summaries = []
    for naive_path in naive_files:
        model_id = parse_model_id_from_filename(naive_path, "naive")
        if not model_id:
            continue
        if args.player_model and model_id != args.player_model:
            continue
        turtle_path = turtle_map.get(model_id)
        source_rows = build_source_rows_for_model(naive_path, turtle_path)
        out_path = make_passk_out_path(args.results_dir, args.dataset_name, model_id, args.judge_model)
        k_m = int((stats.get("k_by_model") or {}).get(model_id, {}).get("k") or stats.get("k_global") or 1)
        s = evaluate_passk_for_model(
            runner=runner,
            model_id=model_id,
            judge_model=args.judge_model,
            source_rows=source_rows,
            out_path=out_path,
            k=k_m,
            temperature=float(args.temperature),
            max_attempts=int(args.max_attempts),
            max_n=int(args.max_n),
            verbose_progress=bool(args.verbose_progress),
        )
        summaries.append(s)
        print(
            f"[INFO] {model_id}: {s['n_correct']}/{s['n_total']} "
            f"acc={s['accuracy']:.3f} -> {s['out_path']}"
        )

    summary_path = os.path.join(args.results_dir, f"{args.dataset_name}__passk_summary.json")
    save_json(summary_path, summaries)
    print(f"[INFO] summary saved: {summary_path}")


if __name__ == "__main__":
    main()
