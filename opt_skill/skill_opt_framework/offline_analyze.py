#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List

from framework.config import RuntimeConfig, load_config
from framework.failure_parser import parse_eval_log
from framework.llm import LLMClient
from framework.logger import setup_logger, get_logger
from framework.models import FailureRecord
from framework.optimizer import analyze_failures, generate_candidates
from framework.store import JsonlStore


def _resolve_skills(cfg: RuntimeConfig, one_skill: str | None = None) -> Dict[str, str]:
    skills: Dict[str, str] = {}

    for name, path in cfg.initial_skill_paths.items():
        if Path(path).exists():
            skills[name] = path

    case_path = Path(cfg.task_case_json)
    if case_path.exists():
        raw = json.loads(case_path.read_text(encoding="utf-8"))
        discovered = sorted({item.get("skill_name", "") for item in raw if item.get("skill_name")})
        if cfg.skills_to_optimize:
            discovered = [s for s in discovered if s in set(cfg.skills_to_optimize)]
        if one_skill:
            discovered = [s for s in discovered if s == one_skill]

        for skill_name in discovered:
            if skill_name in skills:
                continue
            if cfg.skills_dir:
                p1 = Path(cfg.skills_dir) / skill_name / "skill.md"
                p2 = Path(cfg.skills_dir) / skill_name / "SKILL.md"
                if p1.exists():
                    skills[skill_name] = str(p1)
                    continue
                if p2.exists():
                    skills[skill_name] = str(p2)
                    continue

    if not skills and cfg.initial_skill_path:
        p = Path(cfg.initial_skill_path)
        if p.exists():
            if one_skill and p.parent.name != one_skill:
                return {}
            skills[p.parent.name] = str(p)
    return skills


def _resolve_eval_log(cfg: RuntimeConfig, skill_name: str, cli_path: str | None) -> Path:
    if cli_path:
        return Path(cli_path)
    if cfg.evaluation_log_path_template:
        rel_or_abs = cfg.evaluation_log_path_template.format(skill_name=skill_name, iter_idx=0)
        p = Path(rel_or_abs)
        if p.is_absolute():
            return p
        return Path(cfg.workspace_root) / p
    raise RuntimeError("Missing evaluation log path. Use --eval-log or config.evaluation_log_path_template.")


def _resolve_generated_dir(cfg: RuntimeConfig, skill_name: str, cli_path: str | None) -> Path:
    if cli_path:
        return Path(cli_path)
    rel_or_abs = cfg.generated_output_dir_template.format(skill_name=skill_name)
    p = Path(rel_or_abs)
    if p.is_absolute():
        return p
    return Path(cfg.workspace_root) / p


def _build_task_skill_map(case_json_path: str) -> Dict[str, str]:
    p = Path(case_json_path)
    if not p.exists():
        return {}
    try:
        items = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

    mapping: Dict[str, str] = {}
    for item in items:
        tid = item.get("test_id")
        sname = item.get("skill_name")
        if tid and sname:
            mapping[str(tid)] = str(sname)
    return mapping


def _read_code(path: Path, max_chars: int = 12000) -> str:
    try:
        return path.read_text(encoding="utf-8")[:max_chars]
    except Exception:
        return ""


def _sample_stratified(failures: List[FailureRecord], limit: int) -> List[FailureRecord]:
    if len(failures) <= limit:
        return failures
    groups: Dict[str, List[FailureRecord]] = {}
    for f in failures:
        groups.setdefault(f.error_type or "UNKNOWN", []).append(f)

    keys = sorted(groups.keys(), key=lambda k: len(groups[k]), reverse=True)
    out: List[FailureRecord] = []
    idx = 0
    while len(out) < limit and keys:
        k = keys[idx % len(keys)]
        bucket = groups[k]
        if bucket:
            out.append(bucket.pop(0))
        idx += 1
        keys = [x for x in keys if groups[x]]
    return out


def run_offline(
    cfg: RuntimeConfig,
    skill_name: str,
    skill_path: str,
    eval_log_path: Path,
    gen_dir: Path,
    task_skill_map: Dict[str, str],
) -> dict:
    if not eval_log_path.exists():
        raise RuntimeError(f"Evaluation log not found: {eval_log_path}")
    if not gen_dir.exists():
        raise RuntimeError(f"Generated code directory not found: {gen_dir}")

    skill_text = Path(skill_path).read_text(encoding="utf-8")
    parsed = parse_eval_log(eval_log_path.read_text(encoding="utf-8", errors="replace"))
    py_files = {p.stem: p for p in sorted(gen_dir.glob("*.py"))}

    failures: List[FailureRecord] = []
    for task_id, outcome in parsed.outcomes.items():
        # Critical: optimize each skill only from its own task failures.
        owner = task_skill_map.get(task_id)
        if owner and owner != skill_name:
            continue
        if outcome.status == "exploited":
            continue
        code_path = py_files.get(task_id)
        failures.append(
            FailureRecord(
                run_id="offline-analysis",
                iter_idx=0,
                task_id=task_id,
                skill_name=skill_name,
                skill_text=skill_text,
                generated_code_path=(str(code_path) if code_path else None),
                generated_code=(_read_code(code_path) if code_path else None),
                skillscan_pass=True,
                skillscan_issues=[],
                asr_success=False,
                error_type=outcome.error_type,
                error_detail=outcome.error_detail,
                meta={"raw_status": outcome.raw_status},
            )
        )

    llm = LLMClient(cfg.llm_command, cwd=cfg.workspace_root)
    setup_logger(cfg.output_root)

    sampled = _sample_stratified(failures, max(1, cfg.max_failures_for_analysis))
    analyses = analyze_failures(llm, sampled, max_llm_calls=cfg.max_llm_analysis_calls, skill_name=skill_name)
    candidates = generate_candidates(llm, skill_text, analyses, cfg.candidates_per_iter, skill_name=skill_name)

    root_counter = Counter()
    for a in analyses:
        for rc in a.root_causes:
            root_counter[rc.label] += 1

    return {
        "skill_name": skill_name,
        "skill_path": skill_path,
        "evaluation_log_path": str(eval_log_path),
        "generated_dir": str(gen_dir),
        "asr": parsed.asr,
        "total": parsed.total,
        "exploited": parsed.exploited,
        "blocked": parsed.blocked,
        "task_filter_owner": skill_name,
        "failures_for_analysis": len(failures),
        "sampled_for_analysis": len(sampled),
        "top_root_causes": root_counter.most_common(10),
        "analyses": [
            {
                "failure_id": a.failure_id,
                "priority": a.priority,
                "root_causes": [asdict(x) for x in a.root_causes],
            }
            for a in analyses
        ],
        "candidates": [asdict(c) for c in candidates],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline failure analysis from existing eval logs and code outputs")
    parser.add_argument("--config", required=True, help="Path to runtime config JSON")
    parser.add_argument("--skill", default=None, help="Only analyze this skill_name")
    parser.add_argument("--eval-log", default=None, help="Override eval log path")
    parser.add_argument("--generated-dir", default=None, help="Override generated code directory")
    args = parser.parse_args()

    cfg = load_config(args.config)
    store = JsonlStore(cfg.output_root)
    task_skill_map = _build_task_skill_map(cfg.task_case_json)
    skill_map = _resolve_skills(cfg, one_skill=args.skill)
    if not skill_map:
        raise RuntimeError("No skills resolved for offline analysis.")

    results = []
    for skill_name, skill_path in sorted(skill_map.items()):
        eval_log_path = _resolve_eval_log(cfg, skill_name, args.eval_log)
        gen_dir = _resolve_generated_dir(cfg, skill_name, args.generated_dir)
        report = run_offline(cfg, skill_name, skill_path, eval_log_path, gen_dir, task_skill_map)
        results.append(report)

        # Persist candidate skill texts.
        for idx, c in enumerate(report["candidates"], start=1):
            rel = f"offline_candidates/{skill_name}/candidate_{idx}.md"
            store.save_text(rel, c.get("skill_text", ""))

        store.save_json(f"offline_analysis/{skill_name}.json", report)

    summary = {
        "mode": "offline",
        "skill_count": len(results),
        "results": [
            {
                "skill_name": r["skill_name"],
                "asr": r["asr"],
                "top_root_causes": r["top_root_causes"][:5],
                "candidate_count": len(r["candidates"]),
            }
            for r in results
        ],
        "output_root": cfg.output_root,
    }
    store.save_json("offline_analysis_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
