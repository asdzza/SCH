from __future__ import annotations

import shlex
import subprocess
from typing import Dict, List


def run_skillscan(skillscan_command: str, skill_path: str, cwd: str) -> Dict[str, object]:
    cmd = shlex.split(skillscan_command) + [skill_path]
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)

    issues: List[str] = []
    output_lines = (res.stdout + "\n" + res.stderr).splitlines()
    for line in output_lines:
        line = line.strip()
        if not line:
            continue
        if any(k in line.lower() for k in ["error", "warn", "fail", "violation"]):
            issues.append(line)

    return {
        "pass": res.returncode == 0,
        "issues": issues[:30],
        "stdout": res.stdout,
        "stderr": res.stderr,
    }
