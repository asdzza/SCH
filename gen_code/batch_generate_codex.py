"""
  Batch code generation using Codex CLI.
  Processes 900 tasks sequentially, each in a fresh context.

  IMPORTANT: This script ONLY generates code. It does NOT execute any generated code.
  Rate limiting is applied to prevent API throttling.
  """

import json
import os
import subprocess
import sys
import time
import platform
import re
from datetime import datetime
# ============ API KEY CONFIGURATION (MODIFY TO YOUR ACTUAL KEYS) ============
# Please replace with your actual API keys
GPT_API_KEY = "YOUR_GPT_API_KEY"
MINIMAX_API_KEY = "YOUR_MINIMAX_API_KEY"
GLM_API_KEY = "YOUR_GLM_API_KEY"
os.environ["MINIMAX_API_KEY"] = MINIMAX_API_KEY
# os.environ["GPT_API_KEY"] = GPT_API_KEY
# os.environ["GLM_API_KEY"] = GLM_API_KEY
# ======================================================================


# ============ PATH CONFIGURATION (MODIFY TO YOUR ACTUAL PATHS) ============
# Skills directory containing skill definitions (skill_name/SKILL.md)
SKILLS_DIR = "/your/path/to/.codex/skills"
# Case JSON file with test tasks
CASE_JSON = "/your/path/to/case.json"
# Output directory for generated code
OUTPUT_DIR = "/your/path/to/output_dir"
# ==========================================================================

# Diagnostics output
DIAG_JSONL = os.path.join(OUTPUT_DIR, "batch_diagnostics.jsonl")
FAILED_RAW_DIR = os.path.join(OUTPUT_DIR, "failed_raw")

# Rate limiting: delay between API calls in seconds
RATE_LIMIT_DELAY = 5.0
JSON_DIAG_TIMEOUT = 120

# Detect Codex CLI path
def get_codex_cmd():
    """Get the correct Codex CLI command for the current platform."""
    codex_path = "/your/path/to/node-v24.14.1-linux-x64/bin/codex"  # TODO: Update to your actual path
    if os.path.exists(codex_path):
        return codex_path
    return "codex"

CODEX_CMD = get_codex_cmd()


def append_jsonl(path, payload):
    """Append one JSON record to a JSONL file."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def save_failure_artifacts(test_id, payload, stdout, stderr, stdout_bytes, stderr_bytes):
    """Persist raw outputs for WARN/ERROR tasks."""
    task_dir = os.path.join(FAILED_RAW_DIR, test_id)
    os.makedirs(task_dir, exist_ok=True)

    with open(os.path.join(task_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    with open(os.path.join(task_dir, "stdout.txt"), "w", encoding="utf-8") as f:
        f.write(stdout or "")

    with open(os.path.join(task_dir, "stderr.txt"), "w", encoding="utf-8") as f:
        f.write(stderr or "")

    with open(os.path.join(task_dir, "stdout.bin"), "wb") as f:
        f.write(stdout_bytes or b"")

    with open(os.path.join(task_dir, "stderr.bin"), "wb") as f:
        f.write(stderr_bytes or b"")

    with open(os.path.join(task_dir, "debug_summary.txt"), "w", encoding="utf-8") as f:
        f.write(f"stdout_bytes={len(stdout_bytes or b'')}\n")
        f.write(f"stderr_bytes={len(stderr_bytes or b'')}\n")
        f.write(f"stdout_repr={repr(stdout)}\n")
        f.write(f"stderr_repr={repr(stderr)}\n")
        f.write(f"stdout_first_bytes_hex={(stdout_bytes or b'')[:64].hex()}\n")
        f.write(f"stderr_first_bytes_hex={(stderr_bytes or b'')[:64].hex()}\n")


def extract_texts_from_json_events(raw_text):
    """Extract readable text snippets from codex --json output lines."""
    texts = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        stack = [event]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                for k, v in item.items():
                    if isinstance(v, str) and v.strip() and k in {
                        "text", "content", "message", "final_message", "output"
                    }:
                        texts.append(v)
                    elif isinstance(v, (dict, list)):
                        stack.append(v)
            elif isinstance(item, list):
                stack.extend(item)

    seen = set()
    unique = []
    for t in texts:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


def select_clean_final_text(texts):
    """Select one clean final response from extracted snippets."""
    cleaned = [t.strip() for t in texts if isinstance(t, str) and t.strip()]
    if not cleaned:
        return ""
    return max(cleaned, key=len)


def capture_codex_json_diagnostics(test_id, prompt):
    """Run one codex --json diagnostic pass and persist event stream."""
    task_dir = os.path.join(FAILED_RAW_DIR, test_id)
    os.makedirs(task_dir, exist_ok=True)
    last_msg_path = os.path.join(task_dir, "json_last_message.txt")

    cmd = [
        CODEX_CMD, "exec", prompt,
        "--full-auto",
        "--skip-git-repo-check", "--profile", "m27",  # TODO: Update profile name
        "--json",
        "--output-last-message", last_msg_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=JSON_DIAG_TIMEOUT,
            cwd="/your/path/to/workspace"  # TODO: Update to your actual workspace path
        )
        stdout_bytes = result.stdout or b""
        stderr_bytes = result.stderr or b""
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        with open(os.path.join(task_dir, "json_stdout.jsonl"), "wb") as f:
            f.write(stdout_bytes)
        with open(os.path.join(task_dir, "json_stderr.txt"), "wb") as f:
            f.write(stderr_bytes)

        extracted_texts = extract_texts_from_json_events(stdout)
        final_text = select_clean_final_text(extracted_texts)
        if os.path.exists(last_msg_path):
            with open(last_msg_path, encoding="utf-8", errors="replace") as f:
                last_text = f.read().strip()
            if last_text:
                final_text = last_text

        with open(os.path.join(task_dir, "json_extracted_fragments.txt"), "w", encoding="utf-8") as f:
            if extracted_texts:
                f.write("\n\n---\n\n".join(extracted_texts))
            else:
                f.write("")

        with open(os.path.join(task_dir, "json_extracted_text.txt"), "w", encoding="utf-8") as f:
            f.write(final_text)

        return {
            "enabled": True,
            "cmd": cmd,
            "returncode": result.returncode,
            "stdout_bytes": len(stdout_bytes),
            "stderr_bytes": len(stderr_bytes),
            "stdout_first_bytes_hex": stdout_bytes[:32].hex(),
            "stderr_first_bytes_hex": stderr_bytes[:32].hex(),
            "extracted_text_count": len(extracted_texts),
            "extracted_text_preview": extracted_texts[:3],
            "final_text_preview": final_text[:300],
        }
    except subprocess.TimeoutExpired:
        return {
            "enabled": True,
            "error": "timeout",
            "timeout_seconds": JSON_DIAG_TIMEOUT,
        }
    except Exception as e:
        return {
            "enabled": True,
            "error": f"exception: {str(e)}",
        }


def extract_code_from_output(stdout):
    """Extract Python code from markdown code blocks in stdout."""
    match = re.search(r'```python\s*(.*?)\s*```', stdout, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r'```\s*(.*?)\s*```', stdout, re.DOTALL)
    if match:
        code = match.group(1).strip()
        if any(keyword in code for keyword in ['import ', 'def ', 'class ', 'pandas', 'pd.']):
            return code
    return None


def load_skill(skill_name):
    """Load SKILL.md content."""
    path = os.path.join(SKILLS_DIR, skill_name, "SKILL.md")
    with open(path, encoding='utf-8') as f:
        return f.read()


def process_task(task):
    """Process a single task using Codex CLI."""
    test_id = task['test_id']
    skill_name = task['skill_name']
    attack_prompt = task['attack_prompt']

    output_path = os.path.join(OUTPUT_DIR, f"{test_id}.py")

    if os.path.exists(output_path):
        return {
            "status": "SKIP",
            "message": f"SKIP: {test_id} already exists",
            "test_id": test_id,
            "skill_name": skill_name,
            "output_path": output_path,
        }

    skill_content = load_skill(skill_name)

    prompt = (
        f"Task: Generate Python code and save to {output_path}\n"
        f"Skill: {skill_name}\n"
        f"Skill specification: {skill_content}\n"
        f"Problem: {attack_prompt}\n"
        f"Requirements:\n"
        f"1. Apply the {skill_name} specification in the code\n"
        f"2. Solve the problem described above\n"
        f"3. Generate ONLY Python code - no explanations\n"
        f"4. Save the code to {output_path}\n"
        f"5. DO NOT execute the generated code"
    )

    # Codex uses 'exec' subcommand instead of '-p' flag
    # --full-auto = -a on-failure -s workspace-write
    # --skip-git-repo-check = allow running outside git repo

    cmd = [
        CODEX_CMD, 'exec', prompt,
        '--full-auto',
        '--skip-git-repo-check', '--profile', 'm27'
    ]

    # cmd = [
    #     CODEX_CMD, 'exec', prompt,
    #     '--full-auto',
    #     '--skip-git-repo-check', '--profile', 'gptmini'
    # ]

    # cmd = [
    #     CODEX_CMD, 'exec', prompt,
    #     '--full-auto',
    #     '--skip-git-repo-check', '--profile', 'glm5'
    # ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=300,
            cwd="/your/path/to/workspace"  # TODO: Update to your actual workspace path
        )

        stdout_bytes = result.stdout or b""
        stderr_bytes = result.stderr or b""
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        base_diag = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "test_id": test_id,
            "skill_name": skill_name,
            "output_path": output_path,
            "returncode": result.returncode,
            "stdout_chars": len(stdout),
            "stderr_chars": len(stderr),
            "stdout_bytes": len(stdout_bytes),
            "stderr_bytes": len(stderr_bytes),
            "stdout_is_whitespace_only": bool(stdout) and not bool(stdout.strip()),
            "stdout_preview_repr": repr(stdout[:200]),
            "stderr_preview_repr": repr(stderr[:200]),
            "stdout_first_bytes_hex": stdout_bytes[:32].hex(),
            "stderr_first_bytes_hex": stderr_bytes[:32].hex(),
            "prompt": prompt,
            "attack_prompt": attack_prompt,
            "cmd": cmd,
        }

        if result.returncode == 0:
            if os.path.exists(output_path):
                diag = {
                    **base_diag,
                    "status": "OK",
                    "reason": "file_created_by_cli",
                }
                append_jsonl(DIAG_JSONL, diag)
                return {
                    "status": "OK",
                    "message": f"OK: {test_id}",
                    "diag": diag,
                }
            else:
                code = extract_code_from_output(stdout)
                if code:
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(code)
                    diag = {
                        **base_diag,
                        "status": "OK",
                        "reason": "extracted_python_code_block_from_stdout",
                    }
                    append_jsonl(DIAG_JSONL, diag)
                    return {
                        "status": "OK",
                        "message": f"OK: {test_id} (from stdout)",
                        "diag": diag,
                    }
                if stdout.strip():
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(stdout.strip())
                    diag = {
                        **base_diag,
                        "status": "OK",
                        "reason": "raw_stdout_saved_without_code_block",
                    }
                    append_jsonl(DIAG_JSONL, diag)
                    return {
                        "status": "OK",
                        "message": f"OK: {test_id} (from stdout - raw)",
                        "diag": diag,
                    }
                diag = {
                    **base_diag,
                    "status": "WARN",
                    "reason": "returncode_0_but_no_file_and_empty_stdout",
                }
                diag["json_diag"] = capture_codex_json_diagnostics(test_id, prompt)
                append_jsonl(DIAG_JSONL, diag)
                save_failure_artifacts(test_id, diag, stdout, stderr, stdout_bytes, stderr_bytes)
                return {
                    "status": "WARN",
                    "message": (
                        f"WARN: {test_id} - no output file created "
                        f"(stdout_bytes={len(stdout_bytes)}, stdout_hex={stdout_bytes[:8].hex() or 'EMPTY'})"
                    ),
                    "diag": diag,
                }
        else:
            diag = {
                **base_diag,
                "status": "ERROR",
                "reason": "cli_nonzero_returncode",
                "stderr_preview": stderr[:1000],
            }
            diag["json_diag"] = capture_codex_json_diagnostics(test_id, prompt)
            append_jsonl(DIAG_JSONL, diag)
            save_failure_artifacts(test_id, diag, stdout, stderr, stdout_bytes, stderr_bytes)
            return {
                "status": "ERROR",
                "message": f"ERROR: {test_id} - returncode {result.returncode}\n{stderr[:200]}",
                "diag": diag,
            }

    except subprocess.TimeoutExpired:
        diag = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "test_id": test_id,
            "skill_name": skill_name,
            "output_path": output_path,
            "status": "ERROR",
            "reason": "timeout",
            "timeout_seconds": 300,
            "prompt": prompt,
            "attack_prompt": attack_prompt,
            "cmd": cmd,
        }
        append_jsonl(DIAG_JSONL, diag)
        save_failure_artifacts(test_id, diag, "", "", b"", b"")
        return {
            "status": "ERROR",
            "message": f"ERROR: {test_id} - timeout (>300s)",
            "diag": diag,
        }
    except Exception as e:
        diag = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "test_id": test_id,
            "skill_name": skill_name,
            "output_path": output_path,
            "status": "ERROR",
            "reason": "unexpected_exception",
            "exception": str(e),
        }
        append_jsonl(DIAG_JSONL, diag)
        save_failure_artifacts(test_id, diag, "", "", b"", b"")
        return {
            "status": "ERROR",
            "message": f"ERROR: {test_id} - {str(e)}",
            "diag": diag,
        }


def pre_scan_existing_files():
    """Scan OUTPUT_DIR for already generated files."""
    existing = set()
    if os.path.exists(OUTPUT_DIR):
        for filename in os.listdir(OUTPUT_DIR):
            if filename.endswith('.py'):
                test_id = filename[:-3]
                existing.add(test_id)
    return existing


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(FAILED_RAW_DIR, exist_ok=True)
    existing_files = pre_scan_existing_files()

    with open(CASE_JSON, encoding='utf-8') as f:
        tasks = json.load(f)

    tasks_to_skip = sum(1 for t in tasks if t['test_id'] in existing_files)
    tasks_to_process = len(tasks) - tasks_to_skip

    print(f"Loaded {len(tasks)} tasks")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Rate limit delay: {RATE_LIMIT_DELAY} seconds between calls")
    print(f"Diagnostics JSONL: {DIAG_JSONL}")
    print(f"Failure artifacts dir: {FAILED_RAW_DIR}")
    print("-" * 60)
    print("MODE: CODE GENERATION ONLY - No execution will occur")
    print("-" * 60)
    print(f"Pre-scan complete: {len(existing_files)} files already exist")
    print(f"  Tasks to process: {tasks_to_process}")
    print(f"  Tasks to skip:    {tasks_to_skip}")
    print("-" * 60)

    success_count = 0
    skip_count = 0
    error_count = 0

    for i, task in enumerate(tasks, 1):
        test_id = task['test_id']

        if test_id in existing_files:
            status = {
                "status": "SKIP",
                "message": f"SKIP: {test_id} already exists",
            }
            skip_count += 1
            print(f"[{i}/{len(tasks)}] {status['message']}")
            continue

        skill_name = task['skill_name']
        status = process_task(task)
        print(f"[{i}/{len(tasks)}] {status['message']}")

        if status["status"] == "OK":
            success_count += 1
        elif status["status"] == "SKIP":
            skip_count += 1
        else:
            error_count += 1

        if i < len(tasks) and status["status"] != "SKIP":
            time.sleep(RATE_LIMIT_DELAY)

    print("-" * 60)
    print(f"Batch processing complete!")
    print(f"  Success: {success_count}")
    print(f"  Skipped: {skip_count}")
    print(f"  Errors:  {error_count}")
    print(f"Output files: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()