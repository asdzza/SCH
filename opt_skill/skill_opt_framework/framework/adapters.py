from __future__ import annotations

import json
import os
import shlex
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


class CommandError(RuntimeError):
    pass


def run_shell(command: str, cwd: str, env: Optional[Dict[str, str]] = None, timeout: int = 1800) -> subprocess.CompletedProcess:
    cmd = shlex.split(command)
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    result = subprocess.run(
        cmd,
        cwd=cwd,
        env=merged_env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result


def run_generation(
    generate_command: str,
    cwd: str,
    iter_idx: int,
    skill_path: str,
    skill_name: str,
) -> Dict[str, Any]:
    run_id = str(uuid.uuid4())
    env = {
        "OPT_ITER_IDX": str(iter_idx),
        "OPT_SKILL_NAME": skill_name,
        "OPT_SKILL_PATH": skill_path,
        "OPT_RUN_ID": run_id,
    }
    res = run_shell(generate_command, cwd=cwd, env=env)
    return {
        "run_id": run_id,
        "ok": res.returncode == 0,
        "returncode": res.returncode,
        "stdout": res.stdout,
        "stderr": res.stderr,
    }


def run_evaluation(
    evaluate_command: str,
    cwd: str,
    iter_idx: int,
    run_id: str,
    skill_name: str,
    timeout: int = 3600,
) -> Dict[str, Any]:
    env = {
        "OPT_ITER_IDX": str(iter_idx),
        "OPT_SKILL_NAME": skill_name,
        "OPT_RUN_ID": run_id,
    }
    res = run_shell(evaluate_command, cwd=cwd, env=env, timeout=timeout)

    # Optional: evaluator can print a JSON line prefixed with OPT_RESULT:
    parsed_result = None
    for line in res.stdout.splitlines():
        if line.startswith("OPT_RESULT:"):
            payload = line[len("OPT_RESULT:") :].strip()
            try:
                parsed_result = json.loads(payload)
            except json.JSONDecodeError:
                parsed_result = None

    return {
        "ok": res.returncode == 0,
        "returncode": res.returncode,
        "stdout": res.stdout,
        "stderr": res.stderr,
        "parsed_result": parsed_result,
    }


def collect_generated_code(output_dir: str, limit: int = 1000) -> List[Path]:
    p = Path(output_dir)
    if not p.exists():
        return []
    files = sorted(p.glob("*.py"))
    return files[:limit]
