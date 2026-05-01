#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def build_asr_curve(iter_rows: List[Dict[str, Any]]) -> Dict[str, List[Tuple[int, float]]]:
    curves: Dict[str, List[Tuple[int, float]]] = defaultdict(list)
    for row in iter_rows:
        skill = row.get("skill_name", "unknown")
        it = int(row.get("iter_idx", 0))
        summary = row.get("summary", {})
        asr = float(summary.get("best_asr_so_far", 0.0))
        curves[skill].append((it, asr))

    for skill in curves:
        curves[skill] = sorted(curves[skill], key=lambda x: x[0])
    return curves


def save_curves_json(curves: Dict[str, List[Tuple[int, float]]], out_path: Path) -> None:
    data = {k: [{"iter": it, "asr": asr} for it, asr in v] for k, v in curves.items()}
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def render_png_charts(
    curves: Dict[str, List[Tuple[int, float]]],
    failures: List[Dict[str, Any]],
    runs: List[Dict[str, Any]],
    out_dir: Path,
) -> List[str]:
    generated: List[str] = []
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return generated

    # 1) ASR curve per skill
    fig, ax = plt.subplots(figsize=(10, 6))
    for skill, points in sorted(curves.items()):
        if not points:
            continue
        xs = [x for x, _ in points]
        ys = [y for _, y in points]
        ax.plot(xs, ys, marker="o", label=skill)
    ax.set_title("ASR Trend by Skill")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Best ASR So Far")
    ax.grid(True, alpha=0.25)
    if curves:
        ax.legend(fontsize=8)
    p1 = out_dir / "asr_trend_by_skill.png"
    fig.tight_layout()
    fig.savefig(p1, dpi=150)
    plt.close(fig)
    generated.append(str(p1))

    # 2) Failure error type distribution
    err_counts = Counter((x.get("error_type") or "Unknown") for x in failures)
    if err_counts:
        labels = list(err_counts.keys())
        values = [err_counts[k] for k in labels]
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar(labels, values)
        ax.set_title("Failure Error Type Distribution")
        ax.set_ylabel("Count")
        ax.tick_params(axis="x", rotation=30)
        p2 = out_dir / "failure_error_distribution.png"
        fig.tight_layout()
        fig.savefig(p2, dpi=150)
        plt.close(fig)
        generated.append(str(p2))

    # 3) Skillscan reject counts by skill
    reject = Counter()
    for row in runs:
        if row.get("phase") == "candidate_reject" and row.get("reason") == "skillscan_fail":
            reject[row.get("skill_name", "unknown")] += 1

    if reject:
        labels = sorted(reject.keys())
        values = [reject[k] for k in labels]
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar(labels, values)
        ax.set_title("Skillscan Reject Count by Skill")
        ax.set_ylabel("Reject Count")
        ax.tick_params(axis="x", rotation=30)
        p3 = out_dir / "skillscan_reject_by_skill.png"
        fig.tight_layout()
        fig.savefig(p3, dpi=150)
        plt.close(fig)
        generated.append(str(p3))

    return generated


def build_markdown_report(
    final_summary: Dict[str, Any],
    curves: Dict[str, List[Tuple[int, float]]],
    failures: List[Dict[str, Any]],
    runs: List[Dict[str, Any]],
    png_paths: List[str],
) -> str:
    lines: List[str] = []
    lines.append("# Skill Optimization Report")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append(f"- Skill count: {final_summary.get('skill_count', 0)}")
    lines.append(f"- Macro best ASR: {final_summary.get('macro_best_asr', 0.0):.4f}")
    lines.append(f"- Failure records: {len(failures)}")
    lines.append("")

    per_skill = final_summary.get("per_skill", {})
    if per_skill:
        lines.append("## Per-Skill Best Result")
        lines.append("")
        lines.append("| Skill | Best ASR | Skill Hash |")
        lines.append("|---|---:|---|")
        for skill, item in sorted(per_skill.items()):
            lines.append(
                f"| {skill} | {float(item.get('best_asr', 0.0)):.4f} | {item.get('best_skill_hash', '-') } |"
            )
        lines.append("")

    if curves:
        lines.append("## ASR Curves (Text)")
        lines.append("")
        for skill, points in sorted(curves.items()):
            compact = ", ".join([f"iter {i}: {a:.3f}" for i, a in points])
            lines.append(f"- {skill}: {compact}")
        lines.append("")

    err_counts = Counter((x.get("error_type") or "Unknown") for x in failures)
    if err_counts:
        lines.append("## Failure Error Types")
        lines.append("")
        for k, v in err_counts.most_common():
            lines.append(f"- {k}: {v}")
        lines.append("")

    reject = Counter()
    for row in runs:
        if row.get("phase") == "candidate_reject" and row.get("reason") == "skillscan_fail":
            reject[row.get("skill_name", "unknown")] += 1

    if reject:
        lines.append("## Skillscan Rejects")
        lines.append("")
        for k, v in reject.most_common():
            lines.append(f"- {k}: {v}")
        lines.append("")

    if png_paths:
        lines.append("## Charts")
        lines.append("")
        for p in png_paths:
            rel = Path(p).name
            lines.append(f"- ![]({rel})")
        lines.append("")
    else:
        lines.append("## Charts")
        lines.append("")
        lines.append("- matplotlib not available, PNG charts were skipped.")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate visualization report for skill optimization output")
    parser.add_argument("--output-root", required=True, help="Output directory of optimization run")
    parser.add_argument(
        "--report-dir",
        default=None,
        help="Directory to place report files; defaults to <output-root>/report",
    )
    args = parser.parse_args()

    output_root = Path(args.output_root)
    report_dir = Path(args.report_dir) if args.report_dir else output_root / "report"
    report_dir.mkdir(parents=True, exist_ok=True)

    final_path = output_root / "final_summary.json"
    final_summary = {}
    if final_path.exists():
        final_summary = json.loads(final_path.read_text(encoding="utf-8"))

    iter_rows = load_jsonl(output_root / "iterations.jsonl")
    run_rows = load_jsonl(output_root / "runs.jsonl")
    failure_rows = load_jsonl(output_root / "failures.jsonl")

    curves = build_asr_curve(iter_rows)
    save_curves_json(curves, report_dir / "asr_curves.json")

    png_paths = render_png_charts(
        curves=curves,
        failures=failure_rows,
        runs=run_rows,
        out_dir=report_dir,
    )

    md = build_markdown_report(
        final_summary=final_summary,
        curves=curves,
        failures=failure_rows,
        runs=run_rows,
        png_paths=png_paths,
    )
    (report_dir / "report.md").write_text(md, encoding="utf-8")

    summary = {
        "report_dir": str(report_dir),
        "markdown": str(report_dir / "report.md"),
        "asr_curve_json": str(report_dir / "asr_curves.json"),
        "png_charts": png_paths,
    }
    (report_dir / "report_index.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
