"""
benchmark.py (single player+judge per process, sync, resumable, JSON output)

- One Python process runs exactly ONE (player_model, judge_model) pair over all puzzles.
- Output is a SINGLE JSON file (not JSONL).
- Resume is the simplest: if --resume and output JSON exists, we load it and skip
  puzzles whose puzzle_id already appears in results.
- No concurrency/async/threads. Strictly sequential, sync.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple
from tqdm import tqdm
from client import LLMClient
from puzzle_loader import Puzzle, PuzzleLoader


# ===== Prompting =====

def build_player_system_prompt(max_rounds: int) -> str:
    return f"""You are playing a Situation Puzzle (lateral thinking) game as the PLAYER.

Goal: infer the full hidden story by asking the JUDGE yes/no questions, then propose the full solution.

Rules (strict):
- On each turn, output EXACTLY ONE line in one of these formats:
  Q: <one yes/no question ending with a question mark?>
  FINAL: <your complete proposed solution, in plain English>
- Ask only one question per turn.
- Do NOT ask for hints, guidance, or summaries. None will be provided.
- The judge will only reply with one token: YES / NO / BOTH / IRRELEVANT.
- If you send FINAL, the judge will only reply with: CORRECT or INCORRECT.
- You have at most {max_rounds} turns total.

Be efficient: ask discriminative questions. When confident, send FINAL.
"""


def build_player_initial_user(puzzle_setup: str) -> str:
    return f"""PUZZLE SETUP:
{puzzle_setup}

Make your first move now. Remember: output exactly one line starting with 'Q:' or 'FINAL:'.
"""


def build_judge_system_prompt(p: Puzzle) -> str:
    notes_block = f"\n\nNOTES (judge-only):\n{p.notes}" if getattr(p, "notes", "") else ""
    return f"""You are the JUDGE (host) of a Situation Puzzle (lateral thinking) game.

You know the hidden solution. The player does NOT know it.

You MUST follow these rules:
1) If the player message is a yes/no question, answer with EXACTLY ONE token from:
   YES
   NO
   BOTH
   IRRELEVANT
   Output NOTHING else.

2) If the player message starts with "FINAL:", reply with EXACTLY ONE token:
   CORRECT
   INCORRECT
   Output NOTHING else. Do NOT provide explanations.

3) No hints: Never provide hints, guidance, summaries, or extra info.

PUZZLE SETUP (public):
{p.setup}

PUZZLE SOLUTION (secret, judge-only):
{p.solution}{notes_block}
"""


# ===== Parsing / normalization =====

_ALLOWED_QA = ("YES", "NO", "BOTH", "IRRELEVANT")
_ALLOWED_VERDICT = ("CORRECT", "INCORRECT")


def _normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def parse_player_move(text: str) -> Tuple[str, str]:
    """
    Returns (kind, content) where kind is "question" or "final".
    Take first non-empty line. Accept Q:/FINAL: prefixes.
    """
    if not text:
        return "question", "?"

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    first = lines[0] if lines else text.strip()

    upper = first.upper()
    if upper.startswith("FINAL"):
        content = first.split(":", 1)[1].strip() if ":" in first else first[len("FINAL"):].strip()
        return "final", content or ""
    if upper.startswith("Q"):
        content = first.split(":", 1)[1].strip() if ":" in first else first[len("Q"):].strip()
        return "question", content or "?"
    return "question", first


def normalize_judge_qa(text: str) -> str:
    t = _normalize_whitespace((text or "").upper())
    for tok in _ALLOWED_QA:
        if tok in t.split():
            return tok
    return "IRRELEVANT"


def normalize_judge_verdict(text: str) -> str:
    t = _normalize_whitespace((text or "").upper())
    for tok in _ALLOWED_VERDICT:
        if tok in t.split():
            return tok
    return "INCORRECT"


# ===== Single game (sync) =====

def run_single_game(
    client: LLMClient,
    puzzle: Puzzle,
    *,
    player_model: str,
    judge_model: str,
    max_rounds: int,
    player_temperature: float,
) -> Dict[str, Any]:
    judge_messages: List[Dict[str, str]] = [{"role": "system", "content": build_judge_system_prompt(puzzle)}]
    player_messages: List[Dict[str, str]] = [
        {"role": "system", "content": build_player_system_prompt(max_rounds)},
        {"role": "user", "content": build_player_initial_user(puzzle.setup)},
    ]

    history: List[Dict[str, Any]] = []
    success = False
    final_attempt: str = ""
    verdict: str = ""

    for turn in range(1, max_rounds + 1):
        player_raw = client.chat(
            model=player_model,
            msg=player_messages,
            temperature=player_temperature,
        )
        player_messages.append({"role": "assistant", "content": player_raw})

        kind, content = parse_player_move(player_raw)

        if kind == "final":
            final_attempt = content
            judge_messages.append({"role": "user", "content": f"FINAL: {content}"})
            judge_raw = client.chat(
                model=judge_model,
                msg=judge_messages,
                temperature=0.0,
            )
            verdict = normalize_judge_verdict(judge_raw)
            judge_messages.append({"role": "assistant", "content": verdict})

            player_messages.append({"role": "user", "content": verdict})

            history.append({
                "turn": turn,
                "player_raw": player_raw,
                "kind": "final",
                "content": content,
                "judge_raw": judge_raw,
                "judge_norm": verdict,
            })

            if verdict == "CORRECT":
                success = True
                break
            else:
                continue

        # question
        question = content
        judge_messages.append({"role": "user", "content": question})
        judge_raw = client.chat(
            model=judge_model,
            msg=judge_messages,
            temperature=0.0,
        )
        answer = normalize_judge_qa(judge_raw)
        judge_messages.append({"role": "assistant", "content": answer})

        player_messages.append({"role": "user", "content": answer})

        history.append({
            "turn": turn,
            "player_raw": player_raw,
            "kind": "question",
            "content": question,
            "judge_raw": judge_raw,
            "judge_norm": answer,
        })

        # ===== If max_rounds exhausted and still no correct final, force one FINAL =====
    
    if not success:
        forced_turn = max_rounds + 1

        # Ask player for a final explanation now
        player_messages.append({
            "role": "user",
            "content": "You have reached the turn limit. Now provide your complete final solution. "
                       "Output exactly one line starting with 'FINAL:'."
        })
        player_raw = client.chat(
            model=player_model,
            msg=player_messages,
            temperature=player_temperature,
        )
        player_messages.append({"role": "assistant", "content": player_raw})

        # Parse; if not FINAL, still treat the whole line as final content
        kind, content = parse_player_move(player_raw)
        if kind != "final":
            content = player_raw.strip()

        final_attempt = content

        # Judge verdict
        judge_messages.append({"role": "user", "content": f"FINAL: {content}"})
        judge_raw = client.chat(
            model=judge_model,
            msg=judge_messages,
            temperature=0.0,
        )
        verdict = normalize_judge_verdict(judge_raw)
        judge_messages.append({"role": "assistant", "content": verdict})

        # Record
        history.append({
            "turn": forced_turn,
            "player_raw": player_raw,
            "kind": "forced_final",
            "content": content,
            "judge_raw": judge_raw,
            "judge_norm": verdict,
        })

        if verdict == "CORRECT":
            success = True

    return {
        "puzzle": asdict(puzzle),
        "player_model": player_model,
        "judge_model": judge_model,
        "max_rounds": max_rounds,
        "success": success,
        "turns_used": len(history),
        "final_attempt": final_attempt,
        "verdict": verdict,
        "history": history,
    }


# ===== Resume + atomic write =====

def atomic_write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def load_existing(out_path: Path) -> Dict[str, Any]:
    if not out_path.exists():
        return {}
    try:
        with out_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # if file is corrupted, treat as empty (you can also choose to raise)
        return {}


def build_done_puzzle_ids(existing: Dict[str, Any]) -> Set[str]:
    done: Set[str] = set()
    for r in existing.get("results", []) or []:
        pid = (r.get("puzzle") or {}).get("id")
        if pid:
            done.add(pid)
    return done


# ===== Main =====

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--puzzles", type=str, default="data/puzzles_en.json", help="Path to puzzles JSON")
    ap.add_argument("--out", type=str, required=True, help="Output JSON path (one file per player+judge)")
    ap.add_argument("--resume", action="store_true", help="Resume by skipping puzzles already present in output JSON")
    ap.add_argument("--max_rounds", type=int, default=20)
    ap.add_argument("--player_temperature", type=float, default=0.0)

    ap.add_argument("--player_model", type=str, required=True)
    ap.add_argument("--judge_model", type=str, required=True)

    # Provider selection
    ap.add_argument("--provider", choices=["openrouter", "custom"], default="openrouter",
                    help="API provider: openrouter or custom (for Moonshot, DeepSeek, etc.)")

    # OpenRouter settings
    ap.add_argument("--api_key", type=str, default=os.getenv("OPENROUTER_API_KEY", ""), help="API key (env OPENROUTER_API_KEY)")
    ap.add_argument("--base_url", type=str, default=os.getenv("OPENROUTER_BASE_URL", ""), help="Base url (env OPENROUTER_BASE_URL)")

    # Custom provider settings (for Moonshot, etc.)
    ap.add_argument("--custom_api_key", type=str, default=None,
                    help="API key for custom provider (reads from CUSTOM_API_KEY env var if not specified)")
    ap.add_argument("--custom_base_url", type=str, default=None,
                    help="Base URL for custom provider (reads from CUSTOM_BASE_URL env var if not specified)")

    ap.add_argument("--timeout_s", type=float, default=120.0)

    return ap.parse_args()


def main() -> int:
    args = parse_args()

    puzzles = PuzzleLoader(args.puzzles).list()
    out_path = Path(args.out)

    existing: Dict[str, Any] = {}
    done_ids: Set[str] = set()

    if args.resume and out_path.exists():
        existing = load_existing(out_path)
        done_ids = build_done_puzzle_ids(existing)

    # initialize top-level structure
    run_obj: Dict[str, Any] = existing if existing else {
        "player_model": args.player_model,
        "judge_model": args.judge_model,
        "puzzles_path": args.puzzles,
        "max_rounds": args.max_rounds,
        "player_temperature": args.player_temperature,
        "results": [],
        "summary": {},
    }

    # sanity: if resuming into a file from a different model pair, refuse (avoid mixing)
    if args.resume and existing:
        if run_obj.get("player_model") != args.player_model or run_obj.get("judge_model") != args.judge_model:
            raise RuntimeError(
                f"Resume file model mismatch.\n"
                f"File has: player={run_obj.get('player_model')} judge={run_obj.get('judge_model')}\n"
                f"Args have: player={args.player_model} judge={args.judge_model}"
            )

    client = LLMClient(
        provider=args.provider,
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY") if args.provider == "openrouter" else None,
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1") if args.provider == "openrouter" else None,
        custom_api_key=args.custom_api_key or os.environ.get("CUSTOM_API_KEY") if args.provider == "custom" else None,
        custom_base_url=args.custom_base_url or os.environ.get("CUSTOM_BASE_URL") if args.provider == "custom" else None,
    )

    for puz in tqdm(puzzles, desc=f"{args.player_model} doing"):
        pid = getattr(puz, "id", None) or asdict(puz).get("id")
        if args.resume and pid in done_ids:
            continue

        r = run_single_game(
            client,
            puz,
            player_model=args.player_model,
            judge_model=args.judge_model,
            max_rounds=args.max_rounds,
            player_temperature=args.player_temperature,
        )

        run_obj["results"].append(r)
        done_ids.add(pid)

        # checkpoint after each puzzle (simplest resume)
        # also keep summary updated
        n = len(run_obj["results"])
        acc = sum(1 for x in run_obj["results"] if x.get("success")) / max(n, 1)
        run_obj["summary"] = {
            "num_done": n,
            "accuracy": acc,
        }

        atomic_write_json(out_path, run_obj)


    return 0


if __name__ == "__main__":
    raise SystemExit(main())
