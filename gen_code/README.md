# Code Generation Scripts

Batch code generation using Claude Code CLI or Codex CLI. Processes tasks from a case JSON file and outputs generated Python code.

## Scripts

| Script | Backend | Tasks |
|--------|---------|-------|
| `batch_generate_claude.py` | Claude Code CLI | 600 tasks |
| `batch_generate_codex.py` | Codex CLI | 900 tasks |

## Configuration

### batch_generate_claude.py

Update the following placeholders in the `PATH CONFIGURATION` section:

```python
# ============ PATH CONFIGURATION (MODIFY TO YOUR ACTUAL PATHS) ============
SKILLS_DIR = "/your/path/to/.claude/skills"      # TODO: Update
CASE_JSON = "/your/path/to/case.json"            # TODO: Update
OUTPUT_DIR = "/your/path/to/output_dir"          # TODO: Update
# ==========================================================================

# Also update the CLI path in get_claude_cmd():
claude_path = "/your/path/to/claude"  # TODO: Update
```

### batch_generate_codex.py

Update two sections:

**1. API Key Configuration:**
```python
# ============ API KEY CONFIGURATION (MODIFY TO YOUR ACTUAL KEYS) ============
GPT_API_KEY = "YOUR_GPT_API_KEY"
MINIMAX_API_KEY = "YOUR_MINIMAX_API_KEY"  # Active - must set
GLM_API_KEY = "YOUR_GLM_API_KEY"
os.environ["MINIMAX_API_KEY"] = MINIMAX_API_KEY
```

**2. Path Configuration:**
```python
# ============ PATH CONFIGURATION (MODIFY TO YOUR ACTUAL PATHS) ============
SKILLS_DIR = "/your/path/to/.codex/skills"      # TODO: Update
CASE_JSON = "/your/path/to/case.json"           # TODO: Update
OUTPUT_DIR = "/your/path/to/output_dir"         # TODO: Update
# ==========================================================================

# Also update the CLI path in get_codex_cmd():
codex_path = "/your/path/to/node-v24.14.1-linux-x64/bin/codex"  # TODO: Update
```

## Prerequisites

### batch_generate_claude.py
- Claude Code CLI installed (`claude` command)
- Skills directory with `skill_name/SKILL.md` structure
- Case JSON file with task definitions

### batch_generate_codex.py
- Codex CLI installed (`codex` command)
- API keys configured (currently uses MINIMAX_API_KEY)
- Skills directory with `skill_name/SKILL.md` structure
- Case JSON file with task definitions

## Running

```bash
# Generate with Claude Code
python3 batch_generate_claude.py

# Generate with Codex
python3 batch_generate_codex.py
```

## Output Structure

```
<OUTPUT_DIR>/
├── case_001.py          # Generated code files
├── case_002.py
├── ...
├── batch_diagnostics.jsonl    # Diagnostic logs
└── failed_raw/
    ├── case_xxx/               # Failed task artifacts
    │   ├── meta.json
    │   ├── stdout.txt
    │   ├── stderr.txt
    │   └── debug_summary.txt
    └── ...
```

## Case JSON Format

```json
[
  {
    "test_id": "C-001-01",
    "skill_name": "aws-lambda-state-sync",
    "attack_prompt": "Archive a specified project directory...",
    "cia_dimension": "confidentiality",
    "original_task_id": "bcb_14"
  }
]
```

## Rate Limiting

- `batch_generate_claude.py`: 5 second delay between calls (`RATE_LIMIT_DELAY`)
- `batch_generate_codex.py`: 5 second delay between calls (`RATE_LIMIT_DELAY`)

Adjust `RATE_LIMIT_DELAY` based on your API rate limits.

## Notes

- Both scripts ONLY generate code, they do NOT execute generated code
- Skipped tasks (already exist) are reported but not re-processed
- Failed task details are saved to `failed_raw/` for offline analysis

## OpenClaw Experiment

For OpenClaw-based code generation (alternative to Claude Code/Codex CLI), see:
```
./batch_generate_openclaw/README.md
```