import sys
import os
import json
from pathlib import Path

# Add skillscan to Python path
sys.path.append(os.path.join(os.getcwd(), 'skillscan'))

try:
    from SecurityCheck.SkillSecurityScan import SkillSecurityScan
except ImportError:
    print("SkillSecurityScan not found")

try:
    from SecurityCheck.LLMGuard import LLMGuard
except ImportError:
    print("LLMGuard not found")
    LLMGuard = None


def has_skillscan_issue(report_data):
    if not report_data:
        return True

    total_issues = report_data.get("total_issues")
    if isinstance(total_issues, int):
        return total_issues > 0

    issues = report_data.get("issues")
    if isinstance(issues, list):
        return len(issues) > 0

    risk_level = str(report_data.get("risk_level", "")).upper()
    return risk_level not in {"SAFE", ""}


def list_skill_dirs(input_paths):
    if len(input_paths) > 1:
        return [os.path.abspath(p) for p in input_paths if os.path.isdir(p)]

    root = os.path.abspath(input_paths[0])
    if not os.path.isdir(root):
        return []

    child_dirs = [
        os.path.join(root, name)
        for name in os.listdir(root)
        if os.path.isdir(os.path.join(root, name))
    ]

    root_md_count = len(list(Path(root).glob("*.md")))
    if root_md_count == 0 and child_dirs:
        return sorted(child_dirs)

    return [root]

def scan_skill(skill_dir):
    skill_dir = os.path.abspath(skill_dir)
    skill_id = os.path.basename(skill_dir)
    skill_result = {
        "skill_id": skill_id,
        "skill_dir": skill_dir,
        "skillscan_has_issue": True,
        "llmguard_has_issue": False,
        "scan_error": False,
    }
    
    print(f"--- Scanning directory: {skill_dir} ---")
    
    # 1. Run static security scan (skill-security-scan)
    print("\n[1] Running static security scan (skill-security-scan)...")
    scanner = SkillSecurityScan(output_dir=os.path.join(os.getcwd(), 'my_reports'))
    try:
        res = scanner.run_security_scan(skill_dir, skill_id)
        skill_result["skillscan_has_issue"] = has_skillscan_issue(res)
        print("Success! Report saved.")
    except Exception as e:
        skill_result["scan_error"] = True
        print(f"Error running security scan: {e}")

    # 2. Run LLMGuard
    if LLMGuard:
        print("\n[2] Running LLMGuard...")
        guard = LLMGuard()
        
        md_files = list(Path(skill_dir).rglob("*.md"))
        print(f"Found {len(md_files)} Markdown files.")
        
        for md_file in md_files:
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                print(f"Analyzing {md_file.name}...")
                
                sanitized_prompt, results_valid, results_score = guard.sanitize_prompt(content)
                if any(not is_valid for is_valid in results_valid.values()):
                    skill_result["llmguard_has_issue"] = True
                
                output_data = {
                    "file": str(md_file),
                    "results_valid": results_valid,
                    "results_score": results_score
                }
                
                report_path = os.path.join(os.getcwd(), 'my_reports', f"llm_guard_{md_file.name}_report.json")
                os.makedirs(os.path.dirname(report_path), exist_ok=True)
                with open(report_path, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, indent=4)
                    
                print(f"LLMGuard Results for {md_file.name}:")
                for scanner_name, is_valid in results_valid.items():
                    score = results_score.get(scanner_name, 0)
                    status = "✅ PASS" if is_valid else "❌ FAIL"
                    print(f"  - {scanner_name}: {status} (Score: {score:.2f})")
                    
            except Exception as e:
                skill_result["llmguard_has_issue"] = True
                print(f"Error processing {md_file.name} with LLMGuard: {e}")

    return skill_result


def print_summary(skill_results):
    total = len(skill_results)
    if total == 0:
        print("\nNo skills were scanned.")
        return

    skillscan_issue_count = sum(1 for r in skill_results if r["skillscan_has_issue"])
    llmguard_issue_count = sum(1 for r in skill_results if r["llmguard_has_issue"])
    no_issue_count = sum(
        1
        for r in skill_results
        if (not r["skillscan_has_issue"]) and (not r["llmguard_has_issue"])
    )

    summary = {
        "total_skills": total,
        "skillscan_issue_count": skillscan_issue_count,
        "skillscan_issue_ratio": round(skillscan_issue_count / total, 4),
        "llmguard_issue_count": llmguard_issue_count,
        "llmguard_issue_ratio": round(llmguard_issue_count / total, 4),
        "no_issue_count": no_issue_count,
        "no_issue_ratio": round(no_issue_count / total, 4),
        "details": skill_results,
    }

    print("\n========== Final Summary ==========")
    print(f"Total skills scanned: {total}")
    print(
        f"Skills with skillscan issues: {skillscan_issue_count}/{total} "
        f"({summary['skillscan_issue_ratio'] * 100:.2f}%)"
    )
    print(
        f"Skills with LLMGuard issues: {llmguard_issue_count}/{total} "
        f"({summary['llmguard_issue_ratio'] * 100:.2f}%)"
    )
    print(
        f"Skills with no security issues at all: {no_issue_count}/{total} "
        f"({summary['no_issue_ratio'] * 100:.2f}%)"
    )

    summary_path = os.path.join(os.getcwd(), "my_reports", "final_skill_scan_summary.json")
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=4, ensure_ascii=False)
    print(f"Summary report saved to: {summary_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_my_skill.py <path_to_skill_directory_or_root> [more_skill_dirs...]")
    else:
        skill_dirs = list_skill_dirs(sys.argv[1:])
        if not skill_dirs:
            print("No valid skill directory found.")
            sys.exit(1)

        print(f"Will scan {len(skill_dirs)} skill(s).")
        all_results = []
        for skill_dir in skill_dirs:
            all_results.append(scan_skill(skill_dir))

        print_summary(all_results)
