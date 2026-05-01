#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from framework.config import load_config
from framework.orchestrator import OptimizationOrchestrator


def main() -> None:
    parser = argparse.ArgumentParser(description="Skill optimization loop orchestrator")
    parser.add_argument("--config", required=True, help="Path to JSON config")
    args = parser.parse_args()

    cfg = load_config(args.config)
    orchestrator = OptimizationOrchestrator(cfg)
    result = orchestrator.run()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
