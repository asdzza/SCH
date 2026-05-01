#!/usr/bin/env python3
"""LLM call logging for skill optimization debugging.

Logs all prompts sent to the LLM and responses received, including:
- Prompt text (from analysis and candidate generation)
- Raw response text
- Parsed JSON result
- Whether fallback was used
- Error information if any

Output is written to {output_root}/llm_calls.jsonl as newline-delimited JSON.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class LLMCallRecord:
    call_id: str
    timestamp: str
    stage: str  # "analysis" | "candidate" | "fallback"
    skill_name: Optional[str]
    prompt_preview: str  # first 200 chars
    full_prompt: str
    raw_response: str
    parsed_response: Optional[Dict[str, Any]]
    fallback_used: bool
    error: Optional[str]
    call_succeeded: bool

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


class LLMCallLogger:
    """Logs LLM prompts and responses for debugging skill optimization."""

    def __init__(self, output_root: str) -> None:
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.log_path = self.output_root / "llm_calls.jsonl"
        self._buffer: List[Dict[str, Any]] = []
        self._enabled = True

    def log(
        self,
        *,
        stage: str,
        skill_name: Optional[str],
        prompt: str,
        raw_response: str,
        parsed_response: Optional[Dict[str, Any]],
        fallback_used: bool,
        error: Optional[str] = None,
    ) -> None:
        """Record a single LLM interaction."""
        record = LLMCallRecord(
            call_id=str(uuid.uuid4())[:12],
            timestamp=datetime.now().isoformat(timespec="milliseconds"),
            stage=stage,
            skill_name=skill_name,
            prompt_preview=prompt[:200] + ("..." if len(prompt) > 200 else ""),
            full_prompt=prompt,
            raw_response=raw_response,
            parsed_response=parsed_response,
            fallback_used=fallback_used,
            error=error,
            call_succeeded=parsed_response is not None,
        )
        self._buffer.append(record.to_dict())

    def flush(self) -> None:
        """Write buffered records to disk."""
        if not self._buffer:
            return
        with self.log_path.open("a", encoding="utf-8") as f:
            for record in self._buffer:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._buffer.clear()

    def disable(self) -> None:
        self._enabled = False

    def enable(self) -> None:
        self._enabled = True

    @property
    def log_path_str(self) -> str:
        return str(self.log_path)


# Module-level global logger instance
_global_logger: Optional[LLMCallLogger] = None


def setup_logger(output_root: str) -> LLMCallLogger:
    """Initialize the global logger with the given output root."""
    global _global_logger
    _global_logger = LLMCallLogger(output_root)
    return _global_logger


def get_logger() -> Optional[LLMCallLogger]:
    """Get the current global logger, or None if not set up."""
    return _global_logger