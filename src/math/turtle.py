import argparse
import json
import os
import time
from typing import Dict, List, Tuple, Optional

from tqdm import tqdm

# 复用 naive.py 里的工具与 OpenRouter client
from filter import (
    LLMClient,
    extract_after_marker,
    normalize_answer,
    parse_binary_judgement,
)

ALLOWED_JUDGER = ["Yes", "No", "Both", "Irrelevant"]



# -----------------------
# Prompts (English)
# -----------------------
def build_player_system_prompt(max_rounds: int) -> str:
    return f"""You are solving a math problem with help from a Judger in a Situation Puzzle style game.

You have up to {max_rounds} turns of Q&A. The purpose of asking questions is to reduce uncertainty and eliminate wrong solution paths:
- Ask questions that confirm or falsify key hypotheses about the method, intermediate results, constraints, edge cases, etc; or simply guess the answer.
- Avoid vague, open-ended, or multi-part questions.

The Judger will reply with exactly one of: Yes, No, Both, Irrelevant.
Meanings of Judger replies:
- Yes: the proposition in your question is true w.r.t. the correct solution/answer.
- No: it is false.
- Both: partially true / mixed / ambiguous.
- Irrelevant: your question is irrelevant, not answerable as asked, not a yes/no-style question, or asks for forbidden content.

Use those replies to update your understanding and help you solve the problem.

Output format:
- You may think step by step to decide what to ask.
- End your message with exactly ONE of:
  (a) one single yes/no-style question in the format: QQQQ: <your question>, or
  (b) your guessed answer in the format: #### <your answer>. You may guess multiple times, but each guess also consumes one turn.
"""


def build_judger_system_prompt(problem: str, solution: str, exp_ans: str) -> str:
    # Judger must answer only the 4 fixed outputs, no leakage.
    return f"""You are the Judger in a Situation Puzzle style game for a math problem.

You are given:
[Problem]
{problem}

[Official solution / notes] (for your reference only)
{solution}

[Expected final answer] (for your reference only)
{exp_ans}

Your task:
- The player will ask a question (intended to be answerable with Yes/No).
- You MUST reply with EXACTLY ONE of the following strings:
Yes
No
Both
Irrelevant

Meanings:
- Yes: the proposition in the question is true w.r.t. the correct solution/answer.
- No: it is false.
- Both: partially true / mixed / ambiguous.
- Irrelevant: the question is irrelevant, not answerable as asked, not a yes/no-style question, or asks for forbidden content.

Hard constraints:
- Output ONLY one of the 4 strings above. No extra words, no punctuation, no explanations.
- Do NOT reveal the expected answer or the solution.

Rule for '#### <answer>':
- Treat it as a guess attempt. Compare the guessed answer to the expected final answer for equivalence.
- Reply:
  - Yes if the guess is equivalent to the expected answer,
  - No if it is not equivalent,
  - Both if the guess is ambiguous/partially specified,
  - Irrelevant if it cannot be interpreted as an answer.
"""


def sanitize_judger_reply(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return "Irrelevant"
    # 取第一行，尽量避免模型多输出
    first_line = t.splitlines()[0].strip()
    if first_line in ALLOWED_JUDGER:
        return first_line
    # 宽松一点：只要包含某个选项，就用那个（按优先顺序）
    for x in ALLOWED_JUDGER:
        if x in t:
            return x
    return "Irrelevant"


# -----------------------
# Core: turtle-soup solve
# -----------------------
def turtle_soup_solve(
    llm: LLMClient,
    player_model: str,
    judge_model: str,
    problem: str,
    solution: str,
    exp_ans: str,
    max_rounds: int,
) -> Tuple[str, str, List[Dict], int]:
    """
    Returns:
      - final_player_raw: player 最后一次输出（包含 ####）
      - extracted_final: #### 后抽取的最终答案
      - history: [{round, question, judger_reply, player_raw}]
      - questions_used: 实际问了多少轮问题（不含最后强制要答案那次）
    """
    player_msgs = [
        {"role": "system", "content": build_player_system_prompt(max_rounds)},
        {"role": "user", "content": f"Math problem:\n{problem} Please ask a question or guess the answer:"},
    ]

    judger_msgs = [
        {"role": "system", "content": build_judger_system_prompt(problem, solution, exp_ans)}
    ]

    history: List[Dict] = []
    final_player_raw = ""
    extracted_final = ""
    # 最多 max_rounds 个问题轮；任意轮可直接 #### 提交答案
    for r in range(1, max_rounds + 1):
        player_raw = llm.chat(player_model, player_msgs, temperature=0.0).strip()
        player_msgs.append({"role": "assistant", "content": player_raw})
        # print('player msg after player is given context:')
        # print(player_msgs)
        # print('-'*80)

        question = player_raw.strip()

        # ---- 猜答案：只判对错，不走情景推理问答 ----
        if "####" in player_raw:
            idx = question.rfind("####")
            guess_block = player_raw[idx:].strip() if idx != -1 else player_raw.strip()
            guess_answer = extract_after_marker(guess_block, "####")

            judge_raw_01, extracted_j_01, correct_01, status_01 = grade_equivalence(
                llm=llm,
                judge_model=judge_model,
                problem=problem,
                exp_ans=exp_ans,
                model_ans=guess_answer,
            )

            history.append({
                "round": r,
                "type": "guess",
                "player_raw": player_raw,
                "guess_answer": guess_answer,
                "grader_judge_raw": judge_raw_01,
                "grader_extracted": extracted_j_01,
                "grader_correct": correct_01,
                "grader_status": status_01,
            })

            if correct_01 == 1:
                final_player_raw = guess_block
                extracted_final = guess_answer
                questions_used = len(history)
                return final_player_raw, extracted_final, history, questions_used

            # 猜错：不走情景推理问答，直接进入下一轮
            player_msgs.append({"role":"user","content":"Grader verdict: Incorrect."})
            # print("player msgs after checking guessed answer: ")
            # print(player_msgs)
            # print('-' * 80)
            continue


        # ---- 问问题：正常走情景推理问答 ----
        idx = question.rfind("QQQQ:")
        if idx != -1:
            question = question[idx + len("QQQQ:"):].strip()
        judger_msgs.append({"role": "user", "content": f"Player question: {question}"})
        

        judger_raw = llm.chat(judge_model, judger_msgs, temperature=0.0)
        judger_reply = sanitize_judger_reply(judger_raw)
        judger_msgs.append({"role": "assistant", "content": judger_reply})
        player_msgs.append({"role": "user", "content": f"Judger reply: {judger_reply}"})
        # print("player msgs after adding judger response")
        # print(player_msgs)
        # print('-' * 80)

        history.append({
            "round": r,
            "type": "qa",
            "question": question,
            "judger_reply": judger_reply,
            "player_raw": player_raw,
        })

    player_msgs.append({
        "role": "user",
        "content": (
            "No more Q&A turns. Use the interaction history so far, answer the original math problem by reasoning. "
            "At the end of your reasoning, output the final answer on a new line that starts with exactly ####\n"
            "After ####, output ONLY the final answer (no extra words)."
        )
    })


    final_player_raw = llm.chat(player_model, player_msgs, temperature=0.0).strip()
    extracted_final = extract_after_marker(final_player_raw, "####")
    history.append({"round": max_rounds + 1, "type": "final_answer", "player_raw": final_player_raw})

    return final_player_raw, extracted_final, history, max_rounds


# -----------------------
# Grading (same style as naive.py)
# -----------------------
def grade_equivalence(
    llm: LLMClient,
    judge_model: str,
    problem: str,
    exp_ans: str,
    model_ans: str,
) -> Tuple[str, str, int, str]:
    judge_system = (
        "You are a strict grader.\n"
        "Analyze and compare the extracted model answer with the expected answer for equivalence. "
        "Then on a new line output exactly $$$$\n"
        "and after $$$$ output ONLY 1 if equivalent else 0."
    )
    judge_user = (
        f"Problem:\n{problem}\n\n"
        f"Expected answer:\n{exp_ans}\n\n"
        f"Model answer:\n{model_ans}\n\n"
        "Now analyze and compare the answers. After that output $$$$ and give your 0/1 judgement result."
    )
    judge_msgs = [{"role": "system", "content": judge_system}, {"role": "user", "content": judge_user}]
    judge_raw = llm.chat(judge_model, judge_msgs, temperature=0.0).strip()

    extracted_judgement = extract_after_marker(judge_raw, "$$$$")
    correct = parse_binary_judgement(extracted_judgement) if judge_raw else 0
    status = "ok" if judge_raw else "judge_failed"
    return judge_raw, extracted_judgement, correct, status


# -----------------------
# IO helpers
# -----------------------
def make_out_path(out_dir: str, dataset_name: str, provider: str, player_model: str, judge_model: str) -> str:
    safe_player = player_model.replace("/", "_")
    safe_judge = judge_model.replace("/", "_")
    return os.path.join(out_dir, f"{dataset_name}__turtle__{provider}__{safe_player}__judge={safe_judge}.json")


def load_prev(out_path: str) -> Tuple[List[Dict], set]:
    out: List[Dict] = []
    done = set()
    if os.path.exists(out_path):
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                prev = json.load(f)
            if isinstance(prev, list):
                out = prev
                for r in prev:
                    p = (r or {}).get("problem")
                    # 只要已经有 turtle_history / final_player_raw）就算处理过
                    if p and r.get("turtle_history"):
                        done.add(p)
        except Exception:
            pass
    # print(done)
    return out, done


# -----------------------
# Run
# -----------------------
def process_one_row(
    llm: LLMClient,
    args,
    row: Dict,
    processed_problems: set,
) -> Optional[Dict]:
    problem = row.get("problem", "")
    if not problem or problem in processed_problems:
        # print('already done')
        return None

    solution = row.get("solution", "")
    exp_ans = row.get("final_answer", "") or row.get("exp_ans", "")

    final_player_raw, extracted_gen_ans, history, questions_used = turtle_soup_solve(
        llm=llm,
        player_model=args.player_model,
        judge_model=args.judge_model,
        problem=problem,
        solution=solution,
        exp_ans=exp_ans,
        max_rounds=args.max_rounds,
    )
    
    judge_raw, extracted_judgement, correct, status = grade_equivalence(
        llm=llm,
        judge_model=args.judge_model,
        problem=problem,
        exp_ans=exp_ans,
        model_ans=extracted_gen_ans,
    )

    return {
        "problem": problem,
        "solution": solution,
        "exp_ans": exp_ans,
        "gen_ans": final_player_raw,
        "extracted_gen_ans": extracted_gen_ans,
        "turtle_history": history,
        "questions_used": questions_used,
        "judge_raw": judge_raw,
        "extracted_judgement": extracted_judgement,
        "correct": correct,
        "status": status,
        "meta": {
            "method": "turtle",
            "provider": args.provider,
            "player_model": args.player_model,
            "judge_model": args.judge_model,
            "max_rounds": args.max_rounds,
            "ts": time.time(),
        },
    }


def run(args):
    out_dir_abs = os.path.abspath(args.out_dir)
    os.makedirs(out_dir_abs, exist_ok=True)

    out_path = make_out_path(out_dir_abs, args.dataset_name, args.provider, args.player_model, args.judge_model)

    llm = LLMClient(
        provider=args.provider,
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY"),
        openrouter_base_url=args.openrouter_base_url,
    )

    with open(args.dataset_path, "r", encoding="utf-8") as f:
        data_all = json.load(f)
    if args.max_n > 0:
        data_all = data_all[: args.max_n]

    out, processed = load_prev(out_path)

    for row in tqdm(data_all, desc=f"SituationPuzzle {args.dataset_name}"):
        r = process_one_row(llm, args, row, processed)
        if r is None:
            continue
        out.append(r)
        processed.add(r.get("problem", ""))

        # 简单点：每做完一题就覆盖写一次，避免中断丢数据
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"[INFO] saved to: {out_path}")
    total = len(out)
    ok = sum(1 for r in out if int(r.get("correct", 0)) == 1)
    print(f"[INFO] correct: {ok}/{total}")


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset_path", required=True)
    ap.add_argument("--dataset_name", required=True)
    ap.add_argument("--player_model", required=True)
    ap.add_argument("--judge_model", required=True)
    ap.add_argument("--out_dir", default="results")
    ap.add_argument("--max_n", type=int, default=-1)

    ap.add_argument("--max_rounds", type=int, default=20)  # 最多问多少轮
    ap.add_argument("--skip_judge_on_exact_match", action="store_true", default=True)

    ap.add_argument("--provider", choices=["openrouter"], default="openrouter")
    ap.add_argument("--openrouter_base_url", default="https://openrouter.ai/api/v1")
    return ap.parse_args()


def main():
    args = parse_args()
    run(args)


if __name__ == "__main__":
    main()
