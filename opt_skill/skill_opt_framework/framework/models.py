from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class FailureRecord:
    run_id: str
    iter_idx: int
    task_id: str
    skill_name: str
    skill_text: str
    generated_code_path: Optional[str]
    generated_code: Optional[str]
    skillscan_pass: bool
    skillscan_issues: List[str]
    asr_success: bool
    error_type: Optional[str]
    error_detail: Optional[str]
    meta: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RootCause:
    label: str
    confidence: float
    evidence: List[str]
    fix_direction: str


@dataclass
class FailureAnalysis:
    failure_id: str
    root_causes: List[RootCause]
    priority: str


@dataclass
class SkillCandidate:
    candidate_id: str
    parent_skill_hash: str
    skill_text: str
    rationale: str
    expected_gain: str
    content_hash: str = ""  # hash of the raw skill_text (before stripping)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CandidateEval:
    candidate_id: str
    asr: float
    skillscan_pass_rate: float
    total_runs: int
    successes: int
    failures: int
    score: float
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IterationSummary:
    iter_idx: int
    base_skill_hash: str
    candidate_results: List[CandidateEval]
    selected_candidate_id: Optional[str]
    selected_skill_hash: Optional[str]
    best_asr_so_far: float
    notes: str = ""
