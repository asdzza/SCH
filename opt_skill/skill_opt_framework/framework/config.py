from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class RuntimeConfig:
    workspace_root: str
    output_root: str
    task_case_json: str

    generate_command: str
    evaluate_command: str
    skillscan_command: str
    llm_command: str

    # Preferred: optimize all skills in case JSON using this directory.
    skills_dir: Optional[str] = None

    # Optional explicit list of skills to optimize. If empty, auto-discover from case JSON.
    skills_to_optimize: List[str] = field(default_factory=list)

    # Optional override mapping: skill_name -> absolute skill file path.
    initial_skill_paths: Dict[str, str] = field(default_factory=dict)

    # Backward compatibility for single-skill mode.
    initial_skill_path: Optional[str] = None

    # Supports {skill_name} placeholder, relative to workspace_root when not absolute.
    generated_output_dir_template: str = "minimax_a"

    # Optional evaluator log path template. Supports placeholders: {skill_name}, {iter_idx}.
    # Useful when evaluator writes detailed per-task outcomes to file.
    evaluation_log_path_template: Optional[str] = None

    # If true, write current candidate skill text into skills_dir/<skill_name>/SKILL.md
    # before running generation. This supports generators that read fixed skill paths.
    materialize_skill_to_skills_dir: bool = True

    train_sample_size: int = 30
    quick_eval_sample_size: int = 20
    max_iters: int = 8
    candidates_per_iter: int = 4

    objective_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "asr_gain": 1.0,
            "complexity": 0.05,
            "instability": 0.1,
        }
    )

    # If true, only pass failed records to LLM judge.
    use_failures_only: bool = True

    # When failures are huge, sample them before LLM analysis.
    max_failures_for_analysis: int = 120
    max_llm_analysis_calls: int = 30

    random_seed: int = 42


def load_config(path: str) -> RuntimeConfig:
    cfg_path = Path(path)
    with cfg_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    return RuntimeConfig(**raw)
