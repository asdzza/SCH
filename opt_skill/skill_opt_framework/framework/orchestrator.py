from __future__ import annotations

import json
import random
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List

from .config import RuntimeConfig
from .evaluator import evaluate_skill_candidate
from .llm import LLMClient
from .models import CandidateEval, FailureRecord, IterationSummary
from .optimizer import analyze_failures, generate_candidates
from .skillscan import run_skillscan
from .store import JsonlStore, hash_text


class OptimizationOrchestrator:
    def __init__(self, cfg: RuntimeConfig) -> None:
        self.cfg = cfg
        self.store = JsonlStore(cfg.output_root)
        self.llm = LLMClient(cfg.llm_command, cwd=cfg.workspace_root)
        random.seed(cfg.random_seed)

    def _resolve_skills(self) -> Dict[str, str]:
        skills: Dict[str, str] = {}

        # Explicit mapping has highest priority.
        for name, path in self.cfg.initial_skill_paths.items():
            if Path(path).exists():
                skills[name] = path

        case_path = Path(self.cfg.task_case_json)
        if case_path.exists():
            raw = json.loads(case_path.read_text(encoding="utf-8"))
            discovered = sorted({item.get("skill_name", "") for item in raw if item.get("skill_name")})
            if self.cfg.skills_to_optimize:
                discovered = [s for s in discovered if s in set(self.cfg.skills_to_optimize)]

            for skill_name in discovered:
                if skill_name in skills:
                    continue
                if self.cfg.skills_dir:
                    p1 = Path(self.cfg.skills_dir) / skill_name / "skill.md"
                    p2 = Path(self.cfg.skills_dir) / skill_name / "SKILL.md"
                    if p1.exists():
                        skills[skill_name] = str(p1)
                        continue
                    if p2.exists():
                        skills[skill_name] = str(p2)
                        continue

        # Backward compatibility single-skill fallback.
        if not skills and self.cfg.initial_skill_path:
            p = Path(self.cfg.initial_skill_path)
            if p.exists():
                skills[p.parent.name] = str(p)

        if not skills:
            raise RuntimeError("No valid skill files found. Check skills_dir/initial_skill_paths config.")

        return skills

    def _save_candidate_skill(self, skill_name: str, iter_idx: int, candidate_id: str, text: str) -> str:
        rel = f"candidates/{skill_name}/iter_{iter_idx}/{candidate_id}.md"
        return self.store.save_text(rel, text)

    def _log_failures(self, failures: List[FailureRecord]) -> None:
        for f in failures:
            self.store.log_failure(f.to_dict())

    def _sample_failures_for_analysis(self, failures: List[FailureRecord]) -> List[FailureRecord]:
        limit = max(1, int(self.cfg.max_failures_for_analysis))
        if len(failures) <= limit:
            return failures

        # Stratified by error_type so dominant syntax crashes do not hide minority causes.
        groups: Dict[str, List[FailureRecord]] = {}
        for f in failures:
            key = f.error_type or "UNKNOWN"
            groups.setdefault(key, []).append(f)

        ordered_keys = sorted(groups.keys(), key=lambda k: len(groups[k]), reverse=True)
        sampled: List[FailureRecord] = []
        idx = 0
        while len(sampled) < limit and ordered_keys:
            key = ordered_keys[idx % len(ordered_keys)]
            bucket = groups[key]
            if bucket:
                sampled.append(bucket.pop(0))
            idx += 1
            ordered_keys = [k for k in ordered_keys if groups[k]]
        return sampled

    def _guess_eval_log_path(self, skill_name: str, iter_idx: int) -> str | None:
        tpl = self.cfg.evaluation_log_path_template
        if not tpl:
            return None
        rel_or_abs = tpl.format(skill_name=skill_name, iter_idx=iter_idx)
        p = Path(rel_or_abs)
        if p.is_absolute():
            return str(p)
        return str(Path(self.cfg.workspace_root) / p)

    def _materialize_skill_for_generation(self, skill_name: str, source_skill_path: str) -> str:
        if not self.cfg.materialize_skill_to_skills_dir or not self.cfg.skills_dir:
            return source_skill_path

        src = Path(source_skill_path)
        if not src.exists():
            return source_skill_path

        text = src.read_text(encoding="utf-8")
        skill_dir = Path(self.cfg.skills_dir) / skill_name
        p1 = skill_dir / "SKILL.md"
        p2 = skill_dir / "skill.md"

        if p1.exists() or not p2.exists():
            target = p1
        else:
            target = p2

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return str(target)

    def run(self) -> dict:
        skill_map = self._resolve_skills()
        skill_states: Dict[str, Dict[str, object]] = {}

        for skill_name, skill_path in skill_map.items():
            base_text = Path(skill_path).read_text(encoding="utf-8")
            skill_states[skill_name] = {
                "best_skill": base_text,
                "best_asr": 0.0,
                "best_skill_hash": hash_text(base_text),
                "best_skill_path": skill_path,
            }

        for iter_idx in range(1, self.cfg.max_iters + 1):
            for skill_name in sorted(skill_states.keys()):
                state = skill_states[skill_name]
                baseline_skill_path = self._materialize_skill_for_generation(
                    skill_name,
                    str(state["best_skill_path"]),
                )

                baseline_eval, failures, baseline_raw = evaluate_skill_candidate(
                    workspace_root=self.cfg.workspace_root,
                    generate_command=self.cfg.generate_command,
                    evaluate_command=self.cfg.evaluate_command,
                    iter_idx=iter_idx,
                    skill_name=skill_name,
                    skill_path=baseline_skill_path,
                    generated_output_dir=self._guess_generated_dir(skill_name),
                    objective_weights=self.cfg.objective_weights,
                    evaluation_log_path=self._guess_eval_log_path(skill_name, iter_idx),
                )
                baseline_eval.candidate_id = "baseline"

                if baseline_eval.asr >= float(state["best_asr"]):
                    state["best_asr"] = baseline_eval.asr

                self.store.log_run(
                    {
                        "iter_idx": iter_idx,
                        "skill_name": skill_name,
                        "phase": "baseline",
                        "skill_hash": state["best_skill_hash"],
                        "asr": baseline_eval.asr,
                        "score": baseline_eval.score,
                        "raw": baseline_raw,
                    }
                )
                self._log_failures(failures)

                analyze_input = failures if self.cfg.use_failures_only else failures
                analyze_input = self._sample_failures_for_analysis(analyze_input)
                analyses = analyze_failures(
                    self.llm,
                    analyze_input,
                    max_llm_calls=self.cfg.max_llm_analysis_calls,
                )
                candidates = generate_candidates(
                    self.llm,
                    base_skill_text=str(state["best_skill"]),
                    analyses=analyses,
                    k=self.cfg.candidates_per_iter,
                )

                candidate_results: List[CandidateEval] = []
                selected_candidate_id = None
                selected_skill_hash = None

                for c in candidates:
                    skill_path = self._save_candidate_skill(skill_name, iter_idx, c.candidate_id, c.skill_text)
                    eval_skill_path = self._materialize_skill_for_generation(skill_name, skill_path)
                    scan = run_skillscan(self.cfg.skillscan_command, skill_path=skill_path, cwd=self.cfg.workspace_root)

                    if not scan["pass"]:
                        self.store.log_run(
                            {
                                "iter_idx": iter_idx,
                                "skill_name": skill_name,
                                "phase": "candidate_reject",
                                "candidate_id": c.candidate_id,
                                "reason": "skillscan_fail",
                                "scan": scan,
                            }
                        )
                        continue

                    eval_summary, cand_failures, raw = evaluate_skill_candidate(
                        workspace_root=self.cfg.workspace_root,
                        generate_command=self.cfg.generate_command,
                        evaluate_command=self.cfg.evaluate_command,
                        iter_idx=iter_idx,
                        skill_name=skill_name,
                        skill_path=eval_skill_path,
                        generated_output_dir=self._guess_generated_dir(skill_name),
                        objective_weights=self.cfg.objective_weights,
                        evaluation_log_path=self._guess_eval_log_path(skill_name, iter_idx),
                    )
                    eval_summary.candidate_id = c.candidate_id
                    candidate_results.append(eval_summary)

                    self.store.log_run(
                        {
                            "iter_idx": iter_idx,
                            "skill_name": skill_name,
                            "phase": "candidate_eval",
                            "candidate_id": c.candidate_id,
                            "asr": eval_summary.asr,
                            "score": eval_summary.score,
                            "scan": scan,
                            "raw": raw,
                        }
                    )
                    self._log_failures(cand_failures)

                if candidate_results:
                    candidate_results.sort(key=lambda x: x.score, reverse=True)
                    top = candidate_results[0]
                    if top.asr >= float(state["best_asr"]):
                        selected_candidate_id = top.candidate_id
                        match = next((x for x in candidates if x.candidate_id == top.candidate_id), None)
                        if match:
                            state["best_skill"] = match.skill_text
                            state["best_asr"] = top.asr
                            state["best_skill_hash"] = hash_text(match.skill_text)
                            state["best_skill_path"] = self._save_candidate_skill(
                                skill_name,
                                iter_idx,
                                f"best_{match.candidate_id}",
                                match.skill_text,
                            )
                            selected_skill_hash = str(state["best_skill_hash"])

                summary = IterationSummary(
                    iter_idx=iter_idx,
                    base_skill_hash=str(state["best_skill_hash"]),
                    candidate_results=candidate_results,
                    selected_candidate_id=selected_candidate_id,
                    selected_skill_hash=selected_skill_hash,
                    best_asr_so_far=float(state["best_asr"]),
                    notes="",
                )
                self.store.log_iteration(
                    {
                        "iter_idx": iter_idx,
                        "skill_name": skill_name,
                        "summary": {
                            "base_skill_hash": summary.base_skill_hash,
                            "selected_candidate_id": summary.selected_candidate_id,
                            "selected_skill_hash": summary.selected_skill_hash,
                            "best_asr_so_far": summary.best_asr_so_far,
                            "candidate_results": [asdict(c) for c in summary.candidate_results],
                        },
                    }
                )

        per_skill = {}
        for skill_name, state in skill_states.items():
            per_skill[skill_name] = {
                "best_asr": float(state["best_asr"]),
                "best_skill_hash": str(state["best_skill_hash"]),
                "best_skill_path": str(state["best_skill_path"]),
            }

        macro_asr = 0.0
        if per_skill:
            macro_asr = sum(v["best_asr"] for v in per_skill.values()) / len(per_skill)

        final = {
            "macro_best_asr": macro_asr,
            "skill_count": len(per_skill),
            "per_skill": per_skill,
            "output_root": self.cfg.output_root,
        }
        self.store.save_json("final_summary.json", final)
        return final

    def _guess_generated_dir(self, skill_name: str) -> str:
        rel_or_abs = self.cfg.generated_output_dir_template.format(skill_name=skill_name)
        p = Path(rel_or_abs)
        if p.is_absolute():
            return str(p)
        return str(Path(self.cfg.workspace_root) / p)
