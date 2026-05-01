from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from .adapters import collect_generated_code, run_evaluation, run_generation
from .failure_parser import parse_eval_log
from .models import CandidateEval, FailureRecord


def read_code(path: Path, max_chars: int = 12000) -> str:
    try:
        text = path.read_text(encoding="utf-8")
        return text[:max_chars]
    except Exception:
        return ""


def parse_asr_from_eval(parsed_result: Dict[str, Any], fallback_stdout: str) -> float:
    if parsed_result and "asr" in parsed_result:
        try:
            return float(parsed_result["asr"])
        except Exception:
            return 0.0

    # Fallback: find 'ASR: x' in stdout
    for line in fallback_stdout.splitlines():
        lower = line.strip().lower()
        if lower.startswith("asr:"):
            try:
                raw = float(lower.split(":", 1)[1].strip().rstrip("%"))
                return raw / 100.0 if raw > 1.0 else raw
            except Exception:
                continue

        if "dynamic asr" in lower and "%" in lower:
            try:
                val = lower.split(":", 1)[1].split("%", 1)[0].strip()
                raw = float(val)
                return raw / 100.0
            except Exception:
                continue
    return 0.0


def _read_eval_log(evaluation_log_path: str | None) -> str:
    if not evaluation_log_path:
        return ""
    p = Path(evaluation_log_path)
    if not p.exists():
        return ""
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""

    # Append-only logs may contain multiple runs; keep only the latest run block.
    marker = "[*] Starting physical sandbox"
    idx = text.rfind(marker)
    if idx >= 0:
        return text[idx:]
    return text


def evaluate_skill_candidate(
    workspace_root: str,
    generate_command: str,
    evaluate_command: str,
    iter_idx: int,
    skill_name: str,
    skill_path: str,
    generated_output_dir: str,
    objective_weights: Dict[str, float],
    evaluation_log_path: str | None = None,
) -> Tuple[CandidateEval, List[FailureRecord], Dict[str, Any]]:
    gen = run_generation(
        generate_command,
        cwd=workspace_root,
        iter_idx=iter_idx,
        skill_path=skill_path,
        skill_name=skill_name,
    )
    eval_ret = run_evaluation(
        evaluate_command,
        cwd=workspace_root,
        iter_idx=iter_idx,
        run_id=gen["run_id"],
        skill_name=skill_name,
    )

    eval_text = eval_ret.get("stdout", "")
    file_log_text = _read_eval_log(evaluation_log_path)
    merged_log = "\n".join([x for x in [eval_text, file_log_text] if x.strip()])
    parsed_log = parse_eval_log(merged_log) if merged_log.strip() else None

    asr = parse_asr_from_eval(eval_ret.get("parsed_result"), eval_text)
    if parsed_log and parsed_log.asr is not None:
        asr = parsed_log.asr

    files = collect_generated_code(generated_output_dir)
    file_map = {f.stem: f for f in files}
    failures: List[FailureRecord] = []
    skill_text = Path(skill_path).read_text(encoding="utf-8")

    if parsed_log and parsed_log.outcomes:
        for task_id, outcome in parsed_log.outcomes.items():
            if outcome.status == "exploited":
                continue
            code_file = file_map.get(task_id)
            failures.append(
                FailureRecord(
                    run_id=gen["run_id"],
                    iter_idx=iter_idx,
                    task_id=task_id,
                    skill_name=skill_name,
                    skill_text=skill_text,
                    generated_code_path=(str(code_file) if code_file else None),
                    generated_code=(read_code(code_file) if code_file else None),
                    skillscan_pass=True,
                    skillscan_issues=[],
                    asr_success=False,
                    error_type=outcome.error_type,
                    error_detail=outcome.error_detail,
                    meta={
                        "generation_ok": gen["ok"],
                        "evaluation_ok": eval_ret["ok"],
                        "raw_status": outcome.raw_status,
                    },
                )
            )
    else:
        # Fallback behavior when evaluator does not expose per-sample outcomes.
        for f in files:
            code = read_code(f)
            if asr <= 0.0:
                failures.append(
                    FailureRecord(
                        run_id=gen["run_id"],
                        iter_idx=iter_idx,
                        task_id=f.stem,
                        skill_name=skill_name,
                        skill_text=skill_text,
                        generated_code_path=str(f),
                        generated_code=code,
                        skillscan_pass=True,
                        skillscan_issues=[],
                        asr_success=False,
                        error_type=(None if eval_ret["ok"] else "EvalError"),
                        error_detail=(None if eval_ret["ok"] else eval_ret.get("stderr", "")[:1000]),
                        meta={"generation_ok": gen["ok"], "evaluation_ok": eval_ret["ok"]},
                    )
                )

    total = parsed_log.total if parsed_log and parsed_log.total > 0 else max(1, len(files))
    successes = parsed_log.exploited if parsed_log and parsed_log.total > 0 else int(round(asr * total))
    failures_count = max(0, total - successes)

    skillscan_pass_rate = 1.0
    complexity_penalty = len(skill_text) / 5000.0
    instability_penalty = 0.0 if eval_ret["ok"] else 1.0
    score = (
        objective_weights.get("asr_gain", 1.0) * asr
        - objective_weights.get("complexity", 0.05) * complexity_penalty
        - objective_weights.get("instability", 0.1) * instability_penalty
    )

    summary = CandidateEval(
        candidate_id="",
        asr=asr,
        skillscan_pass_rate=skillscan_pass_rate,
        total_runs=total,
        successes=successes,
        failures=failures_count,
        score=score,
        detail={
            "generate_ok": gen["ok"],
            "evaluate_ok": eval_ret["ok"],
            "generate_returncode": gen["returncode"],
            "evaluate_returncode": eval_ret["returncode"],
            "evaluation_log_path": evaluation_log_path,
            "parsed_task_outcomes": (len(parsed_log.outcomes) if parsed_log else 0),
        },
    )

    raw = {
        "generation": gen,
        "evaluation": eval_ret,
        "parsed_evaluation": (
            {
                "asr": parsed_log.asr,
                "total": parsed_log.total,
                "exploited": parsed_log.exploited,
                "blocked": parsed_log.blocked,
            }
            if parsed_log
            else None
        ),
    }
    return summary, failures, raw
