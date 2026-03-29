import argparse
import json
import os
import re
import time
from dotenv import load_dotenv

from tqdm import tqdm

# ---------- Optional deps ----------
# provider=openrouter -> 需要 openai
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

load_dotenv()


# -----------------------
# Utils
# -----------------------
def extract_after_marker(s: str, marker: str) -> str:
    if not s:
        return ""
    idx = s.find(marker)
    if idx == -1:
        return s.strip()
    return s[idx + len(marker) :].strip()


def parse_binary_judgement(text: str) -> int:
    t = (text or "").strip()
    if not t:
        return 0
    first = t.split()[0][:1]
    return 1 if first == "1" else 0


def normalize_answer(s: str) -> str:
    if not s:
        return ""
    s = s.strip()
    s = re.sub(r"\s+", "", s)
    return s


def is_done_but_wrong(r: dict) -> bool:
    """
    “做了但做错了”：
    - player 有可抽取的有效答案 extracted_gen_ans 非空
    - judge 实际执行且返回有效判断：status=="ok" 且 judge_raw 不是 SKIPPED_*
    - extracted_judgement 非空
    - 最终判错 correct==0
    """
    if not isinstance(r, dict):
        return False
    if r.get("status") != "ok":
        return False
    if int(r.get("correct", 0)) != 0:
        return False

    extracted = r.get("extracted_gen_ans", "")
    if not normalize_answer(extracted):
        return False

    judge_raw = (r.get("judge_raw") or "").strip()
    if not judge_raw:
        return False
    if judge_raw.startswith("SKIPPED_"):
        return False

    extracted_j = (r.get("extracted_judgement") or "").strip()
    if not extracted_j:
        return False

    return True

# 断点续跑：读取 out_path 里已处理的数据（仅当输出合法才算“已处理”）
def is_valid_record(rec: dict) -> bool:
    if not isinstance(rec, dict):
        return False
    # 你要求的“合法输出”最小条件：gen_ans 非空
    if not (rec.get("gen_ans") or "").strip():
        return False
    # 可选：如果你还想要求 judge 也跑通，再打开这行
    if not (rec.get("judge_raw") or "").strip():
        return False
    return True
# -----------------------
# Providers
# -----------------------
class LLMClient:
    """
    Unified chat() interface:
      - provider=openrouter: OpenAI-compatible via OpenRouter
      - provider=custom: Custom OpenAI-compatible API (e.g., Moonshot, DeepSeek)
    """

    def __init__(self, provider: str, openrouter_api_key: str = None, openrouter_base_url: str = None,
                 custom_api_key: str = None, custom_base_url: str = None):
        self.provider = provider

        self.openrouter_client = None
        if provider == "openrouter":
            if OpenAI is None:
                raise RuntimeError("provider=openrouter requires 'openai' package. pip install openai")
            if not openrouter_api_key:
                raise RuntimeError("OPENROUTER_API_KEY is missing.")
            self.openrouter_client = OpenAI(
                base_url=openrouter_base_url or "https://openrouter.ai/api/v1",
                api_key=openrouter_api_key,
            )
        elif provider == "custom":
            if OpenAI is None:
                raise RuntimeError("provider=custom requires 'openai' package. pip install openai")
            if not custom_api_key:
                raise RuntimeError("CUSTOM_API_KEY is missing for custom provider.")
            if not custom_base_url:
                raise RuntimeError("CUSTOM_BASE_URL is missing for custom provider.")
            self.openrouter_client = OpenAI(
                base_url=custom_base_url,
                api_key=custom_api_key,
            )
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def chat(self, model: str, msg, temperature: float = 0.0, max_tokens: int = 1000) -> str:
        if self.provider in ["openrouter", "custom"]:
            return self._chat_openrouter(model, msg, temperature=temperature, max_tokens=max_tokens)
        raise ValueError(f"Unknown provider: {self.provider}")

    def _chat_openrouter(self, model, msg, temperature=0.0, max_tokens=1000):
        r = self.openrouter_client.chat.completions.create(
            model=model,
            messages=msg,
            temperature=temperature,
            # max_tokens=max_tokens,
        )
        content = (r.choices[0].message.content or "").strip()
        # print('model_output: ', content)
        return content


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset_path", required=True)
    ap.add_argument("--dataset_name", required=True)
    ap.add_argument("--player_model", required=True)
    ap.add_argument("--judge_model", required=True)
    ap.add_argument("--out_dir", default="results")
    ap.add_argument("--max_n", type=int, default=-1)

    ap.add_argument("--max_attempts", type=int, default=3)
    ap.add_argument("--skip_judge_on_exact_match", action="store_true", default=True)

    ap.add_argument("--provider", choices=["openrouter", "custom"], default="openrouter",
                    help="API provider: openrouter or custom (for Moonshot, DeepSeek, etc.)")
    ap.add_argument("--max_tokens", type=int, default=3000)
    ap.add_argument("--openrouter_base_url", default="https://openrouter.ai/api/v1")
    ap.add_argument("--custom_api_key", default=None,
                    help="API key for custom provider (reads from CUSTOM_API_KEY env var if not specified)")
    ap.add_argument("--custom_base_url", default=None,
                    help="Base URL for custom provider (reads from CUSTOM_BASE_URL env var if not specified)")

    # wrong_limit: “做了但做错了”的题目总数上限（包含断点续传中既有的做错记录）
    ap.add_argument("--wrong_limit", type=int, default=-1)

    args = ap.parse_args()

    # Initialize LLM client based on provider
    if args.provider == "custom":
        api_key = args.custom_api_key or os.environ.get("CUSTOM_API_KEY")
        base_url = args.custom_base_url or os.environ.get("CUSTOM_BASE_URL")
        llm = LLMClient(
            provider=args.provider,
            custom_api_key=api_key,
            custom_base_url=base_url,
        )
    else:  # openrouter
        llm = LLMClient(
            provider=args.provider,
            openrouter_api_key=os.environ.get("OPENROUTER_API_KEY"),
            openrouter_base_url=args.openrouter_base_url,
        )

    out_dir_abs = os.path.abspath(args.out_dir)
    os.makedirs(out_dir_abs, exist_ok=True)

    with open(args.dataset_path, "r", encoding="utf-8") as f:
        data_all = json.load(f)

    if args.max_n > 0:
        data_all = data_all[: args.max_n]

    # 输出路径就是 output_file：直接覆盖该文件；同时支持断点续跑（先读旧文件再写回）
    out_path = os.path.join(
        out_dir_abs,
        f"{args.dataset_name}__{args.provider}__{args.player_model.replace('/', '_')}__judge={args.judge_model.replace('/', '_')}.json",
    )

    print(f"[INFO] provider={args.provider}")
    print(f"[INFO] dataset size: {len(data_all)} (max_n={args.max_n})")
    print(f"[INFO] max_attempts={args.max_attempts}")
    print(f"[INFO] wrong_limit={args.wrong_limit}")
    print(f"[INFO] out_path={out_path}")

    # 断点续跑：读取 out_path 里已处理的数据
    processed_problems = set()
    out = []
    if os.path.exists(out_path):
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                prev = json.load(f)
            if isinstance(prev, list):
                out = prev
                valid_cnt = 0
                for record in prev:
                    p = record.get("problem")
                    if p and is_valid_record(record):
                        processed_problems.add(p)
                        valid_cnt += 1
                print(f"[INFO] resume: loaded {len(out)} existing records from {out_path} (valid={valid_cnt})")
        except Exception as e:
            print(f"[WARN] failed to load existing out_path, will overwrite. err={e}")

    # ✅ wrong_limit 计数：只统计“做了但做错了”的合法记录
    # （否则你之前网络导致 gen_ans 为空，也可能被错误计入）
    naive_wrong_collected = sum(1 for r in out if is_valid_record(r) and is_done_but_wrong(r))
    wrong_limit = int(args.wrong_limit) if args.wrong_limit is not None else -1
    print(f"[INFO] resume_wrong_count={naive_wrong_collected}")

    # 如果断点续传时已经达到 wrong_limit，直接停止，不再继续跑
    if wrong_limit > 0 and naive_wrong_collected >= wrong_limit:
        print("[INFO] early stop: already reached wrong_limit in existing results.")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=4)
        print(f"[INFO] output kept at: {out_path}")
        return
    
    def chat_with_retry(model, messages, *, temperature=0.0, max_tokens=1000, tag=""):
        """
        如果 API 返回空字符串 / 全空白，或抛异常，则自动重试。
        不做超时控制，只做重试与轻量退避。
        """
        last_err = None
        for attempt in range(1, int(args.max_attempts) + 1):
            try:
                text = llm.chat(model, messages, temperature=temperature, max_tokens=max_tokens)
                if (text or "").strip():
                    return text.strip()
                last_err = RuntimeError("empty_response")
            except Exception as e:
                last_err = e

            # 轻量退避：1s, 2s, 3s...（你也可以改成常数 1s）
            if attempt < int(args.max_attempts):
                time.sleep(attempt)

        # 重试耗尽：返回空串，让下游按原逻辑进入 format_error / judge_failed
        print(f"[WARN] chat_with_retry failed after {args.max_attempts} attempts. tag={tag} err={last_err}")
        return ""


    def process_one(row):
        problem = row.get("problem", "")
        if ("correct" in row) and ("judge_raw" in row) and ("extracted_gen_ans" in row):
            if not is_done_but_wrong(row):
                print("skip because not wrong by previous model")
                return None
        if problem in processed_problems:
            return None  # 已处理过
        

        solution = row.get("solution", "")
        exp_ans = row.get("final_answer", "") or row.get("exp_ans")

        # ---- player ----
        player_msgs = [
            {
                "role": "system",
                "content": (
                    "You are a math solver. You should answer the question by reasoning.\n"
                    "At the end of your reasoning, output the final answer on a new line that starts with exactly ####\n"
                    "After ####, output ONLY the final answer (no extra words)."
                ),
            },
            {"role": "user", "content": problem},
        ]
        gen_ans = chat_with_retry(
            args.player_model,
            player_msgs,
            temperature=1.0 if 'kimi' in args.player_model.lower() else 0.0,
            max_tokens=args.max_tokens,
            tag="player",
        )
        extracted_gen_ans = extract_after_marker(gen_ans, "####")

        # skip-judge fast paths
        if args.skip_judge_on_exact_match and normalize_answer(extracted_gen_ans) and (
            normalize_answer(extracted_gen_ans) == normalize_answer(exp_ans)
        ):
            return {
                "problem": problem,
                "solution": solution,
                "exp_ans": exp_ans,
                "gen_ans": gen_ans,
                "extracted_gen_ans": extracted_gen_ans,
                "judge_raw": "SKIPPED_EXACT_MATCH",
                "extracted_judgement": "1",
                "correct": 1,
                "status": "ok_exact_match",
                "meta": {
                    "provider": args.provider,
                    "player_model": args.player_model,
                    "judge_model": args.judge_model,
                    "ts": time.time(),
                },
            }

        if not normalize_answer(extracted_gen_ans):
            # player 没给出有效可抽取答案（格式错/未按要求输出等）
            return {
                "problem": problem,
                "solution": solution,
                "exp_ans": exp_ans,
                "gen_ans": gen_ans,
                "extracted_gen_ans": extracted_gen_ans,
                "judge_raw": "SKIPPED_EMPTY_EXTRACTED_ANSWER",
                "extracted_judgement": "0",
                "correct": 0,
                "status": "format_error_empty_extracted_answer",
                "meta": {
                    "provider": args.provider,
                    "player_model": args.player_model,
                    "judge_model": args.judge_model,
                    "ts": time.time(),
                },
            }

        # ---- judge ----
        judge_system = (
            "You are a strict grader.\n"
            "Analyze and compare the extracted model answer with the expected answer for equivalence. "
            "Then on a new line output exactly $$$$\n"
            "and after $$$$ output ONLY 1 if equivalent else 0."
        )
        judge_user = (
            f"Problem:\n{problem}\n\n"
            f"Expected answer:\n{exp_ans}\n\n"
            f"Model answer:\n{extracted_gen_ans}\n\n"
            "Now analyze and compare the answers. After that output $$$$ and give your 0/1 judgement result."
        )

        judge_msgs = [{"role": "system", "content": judge_system}, {"role": "user", "content": judge_user}]
        judge_raw = chat_with_retry(
            args.judge_model,
            judge_msgs,
            temperature=1.0 if 'kimi' in args.judge_model.lower() else 0.0,
            max_tokens=args.max_tokens,
            tag="judge",
        )


        extracted_judgement = extract_after_marker(judge_raw, "$$$$")
        correct = parse_binary_judgement(extracted_judgement) if judge_raw.strip() else 0
        print(f"judge result for current question: {correct}")
        status = "ok" if judge_raw.strip() else "judge_failed"

        return {
            "problem": problem,
            "solution": solution,
            "exp_ans": exp_ans,
            "gen_ans": gen_ans,
            "extracted_gen_ans": extracted_gen_ans,
            "judge_raw": judge_raw,
            "extracted_judgement": extracted_judgement,
            "correct": correct,
            "status": status,
            "meta": {
                "provider": args.provider,
                "player_model": args.player_model,
                "judge_model": args.judge_model,
                "ts": time.time(),
            },
        }

    # -----------------------
    # Loop + early stop
    # -----------------------
    for row in tqdm(data_all, desc=f"Answering Problems from {args.dataset_name}"):
        # ✅ 再保险：每轮开始前检查（避免刚好达到阈值还多跑一题）
        if wrong_limit > 0 and naive_wrong_collected >= wrong_limit:
            print("[INFO] early stop: reached wrong_limit, stop processing further problems.")
            break

        r = process_one(row)
        if r is None:
            continue
        out.append(r)
        processed_problems.add(r.get("problem", ""))

        if is_done_but_wrong(r):
            naive_wrong_collected += 1
            print(f"[INFO] naive_wrong_collected={naive_wrong_collected}")

    print(f"[INFO] naive_wrong_collected={naive_wrong_collected} (wrong_limit={wrong_limit})")

    # 直接覆盖 out_path（即 output_file）
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=4)

    wrong_cnt_ok = sum(1 for r in out if (r.get("status") == "ok" and int(r.get("correct", 0)) == 0))
    print(f"[INFO] total wrong (judge ok): {wrong_cnt_ok} / {len(out)}")
    print(f"[INFO] output saved to: {out_path}")


if __name__ == "__main__":
    main()
