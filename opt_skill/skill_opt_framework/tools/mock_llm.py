#!/usr/bin/env python3
from __future__ import annotations

import json
import sys


def main() -> None:
    raw = sys.stdin.read().strip()
    if not raw:
        print(json.dumps({"error": "empty prompt"}))
        return

    # Heuristic mock mode: if prompt asks for candidates, return candidates schema.
    lower = raw.lower()
    if "candidates" in lower:
        out = {
            "candidates": [
                {
                    "skill_text": "[Optimized Skill Variant A]\n- Clarify trigger conditions\n- Keep execution path concise\n- Reduce conflicting instructions",
                    "rationale": "Improve trigger clarity and reduce conflict.",
                    "expected_gain": "Higher activation rate"
                },
                {
                    "skill_text": "[Optimized Skill Variant B]\n- Strengthen task-context binding\n- Add deterministic action order\n- Remove redundant constraints",
                    "rationale": "Increase determinism and relevance.",
                    "expected_gain": "Lower failure variance"
                }
            ]
        }
        print(json.dumps(out, ensure_ascii=False))
        return

    # Default: return root-cause analysis schema.
    out = {
        "root_causes": [
            {
                "label": "TRIGGER_MISSING",
                "confidence": 0.77,
                "evidence": ["Generated code did not reflect expected behavior."],
                "fix_direction": "Add explicit trigger patterns and execution hints"
            },
            {
                "label": "OVERSPECIFIED_CONFLICT",
                "confidence": 0.62,
                "evidence": ["Skill contains mutually constraining statements."],
                "fix_direction": "Remove conflicting clauses and simplify ordering"
            }
        ],
        "priority": "high"
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
