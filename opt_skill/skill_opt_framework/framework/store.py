from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class JsonlStore:
    def __init__(self, output_root: str) -> None:
        self.root = Path(output_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _append_jsonl(self, filename: str, row: Dict[str, Any]) -> None:
        path = self.root / filename
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def log_run(self, row: Dict[str, Any]) -> None:
        self._append_jsonl("runs.jsonl", row)

    def log_failure(self, row: Dict[str, Any]) -> None:
        self._append_jsonl("failures.jsonl", row)

    def log_iteration(self, row: Dict[str, Any]) -> None:
        self._append_jsonl("iterations.jsonl", row)

    def save_text(self, rel_path: str, content: str) -> str:
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return str(path)

    def save_json(self, rel_path: str, content: Dict[str, Any]) -> str:
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def load_jsonl(self, filename: str) -> List[Dict[str, Any]]:
        path = self.root / filename
        if not path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        return rows
