from __future__ import annotations

import json
import shlex
import subprocess
from typing import Any, Dict, Optional

from .logger import get_logger


class LLMClient:
    """A command-based LLM client.

    The configured command should read prompt from stdin and output JSON to stdout.
    """

    def __init__(self, llm_command: str, cwd: str) -> None:
        self.llm_command = llm_command
        self.cwd = cwd

    def ask_json(
        self,
        prompt: str,
        fallback: Dict[str, Any],
        *,
        stage: str = "unknown",
        skill_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        logger = get_logger()
        raw_response = ""
        parsed: Optional[Dict[str, Any]] = None
        fallback_used = False

        cmd = shlex.split(self.llm_command)
        try:
            res = subprocess.run(
                cmd,
                cwd=self.cwd,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=360,
            )
        except Exception as e:
            if logger:
                logger.log(
                    stage=stage,
                    skill_name=skill_name,
                    prompt=prompt,
                    raw_response="",
                    parsed_response=None,
                    fallback_used=True,
                    error=f"subprocess exception: {e}",
                )
                logger.flush()
            return fallback

        if res.returncode != 0:
            fallback_used = True
            raw_response = (res.stdout or "") + (res.stderr or "")

        raw = (res.stdout or "").strip()
        stderr_content = (res.stderr or "").strip()

        if not raw:
            fallback_used = True
            raw_response = (res.stdout or "") + (res.stderr or "")
            if logger:
                logger.log(
                    stage=stage,
                    skill_name=skill_name,
                    prompt=prompt,
                    raw_response=raw_response,
                    parsed_response=None,
                    fallback_used=True,
                    error="empty response",
                )
                logger.flush()
            return fallback

        # Prepend stderr (contains thinking content) to raw_response for logging
        raw_response = raw
        if stderr_content:
            raw_response = stderr_content + "\n" + raw_response

        # Try direct JSON
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Try to extract the largest JSON object in output
        if parsed is None:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                snippet = raw[start : end + 1]
                try:
                    parsed = json.loads(snippet)
                except json.JSONDecodeError:
                    pass

        if parsed is None:
            fallback_used = True

        if logger:
            logger.log(
                stage=stage,
                skill_name=skill_name,
                prompt=prompt,
                raw_response=raw_response,
                parsed_response=parsed,
                fallback_used=fallback_used,
                error=None,
            )
            logger.flush()

        return parsed if parsed is not None else fallback
