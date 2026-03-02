"""
puzzle_loader.py

Loads Situation Puzzle (lateral thinking) puzzles from a JSON file.

Expected JSON format: a list of objects:
[
  {
    "id": "string",
    "title": "string",
    "setup": "string",
    "solution": "string",
    "notes": "string (optional)"
  },
  ...
]
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Puzzle:
    id: str
    title: str
    setup: str
    solution: str
    notes: str = ""


class PuzzleLoader:
    def __init__(self, json_path: str | Path) -> None:
        self.json_path = Path(json_path)
        self._puzzles: List[Puzzle] = []
        self._by_id: Dict[str, Puzzle] = {}
        self._load()

    def _load(self) -> None:
        if not self.json_path.exists():
            raise FileNotFoundError(f"Puzzle file not found: {self.json_path}")

        data = json.loads(self.json_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("Puzzle JSON must be a list of objects")

        puzzles: List[Puzzle] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            pid = str(item.get("id", "")).strip()
            title = str(item.get("title", "")).strip()
            setup = str(item.get("setup", "")).strip()
            solution = str(item.get("solution", "")).strip()
            notes = str(item.get("notes", "") or "").strip()

            if not pid or not title or not setup or not solution:
                raise ValueError(f"Invalid puzzle entry (missing fields): {item}")

            puzzles.append(Puzzle(id=pid, title=title, setup=setup, solution=solution, notes=notes))

        # Deterministic order as provided by file
        self._puzzles = puzzles
        self._by_id = {p.id: p for p in puzzles}

    def list(self) -> List[Puzzle]:
        return list(self._puzzles)

    def get(self, puzzle_id: str) -> Optional[Puzzle]:
        return self._by_id.get(puzzle_id)
