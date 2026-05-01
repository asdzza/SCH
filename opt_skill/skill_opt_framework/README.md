# Skill Optimization Framework (Python)

This framework automates a closed loop:

1. Run generation + evaluation with a base skill.
2. Extract failed cases.
3. Ask an LLM to analyze root causes.
4. Ask an LLM to generate candidate skill revisions.
5. Filter candidates by skill scan.
6. Re-run experiments and select the best candidate by score.

New in this version:

- Parse evaluator logs into per-task outcomes (`EXPLOITED` / `BLOCKED`).
- Bind each failed task to generated code + parsed error cause.
- Use stratified failure sampling before LLM analysis.
- Add heuristic root-cause mapping for common failure classes.

It supports multi-skill optimization by discovering `skill_name` from the case JSON and optimizing each skill independently.

## Directory

- `main.py`: CLI entry
- `framework/`: core modules
- `config.example.json`: runnable config template
- `tools/mock_llm.py`: local mock LLM adapter
- `generate_report.py`: visualization report generator

## Quick Start

```bash
cd ./skill_opt_framework
python3 tools/mock_llm.py <<< '{"ping":1}'
python3 main.py --config config.example.json
python3 generate_report.py --output-root ./skill_opt_framework/output
```

## Offline Analysis (No Re-run)

You can analyze existing failures/logs without re-running generation or evaluation:

```bash
cd ./skill_opt_framework
python3 offline_analyze.py --config config.example.json
```

Optional overrides:

```bash
python3 offline_analyze.py \
	--config config.example.json \
	--skill dynamic-feature-flag-loader \
	--eval-log ./claude_gen_code/eval_glm_i.log \
	--generated-dir ./claude_gen_code/gpt_ci
```

Offline outputs:

- `output/offline_analysis/<skill_name>.json`: parsed failures + root causes + candidate skills
- `output/offline_candidates/<skill_name>/candidate_*.md`: candidate skill drafts
- `output/offline_analysis_summary.json`: summary across skills

## Integration Notes

- `generate_command` should run your generation script.
- `evaluate_command` should run your ASR evaluation script.
- This framework does NOT require launching an agent for optimization LLM calls; `llm_command` only needs to call a model API and print JSON.
- The framework passes environment variables `OPT_SKILL_NAME`, `OPT_SKILL_PATH`, `OPT_ITER_IDX`, `OPT_RUN_ID`.
- For multi-skill isolation, configure `generated_output_dir_template` to route each skill to separate output directories when possible.
- If evaluator can print `OPT_RESULT:{"asr": 0.42}` in stdout, parsing is more reliable.
- `skillscan_command` should accept `skillscan <skill_path>` style invocation.
- `evaluation_log_path_template` can point to evaluator logs (for example `eval_glm_i.log`) and supports `{skill_name}` / `{iter_idx}` placeholders.
- `materialize_skill_to_skills_dir=true` writes the current candidate back to `skills_dir/<skill>/SKILL.md` before generation. This is important for generators like `batch_generate.py` that load skills from fixed paths.
- `max_failures_for_analysis` and `max_llm_analysis_calls` control analysis cost while keeping error-type coverage.

## MiniMax-M2.7 API Setup

Install dependency:

```bash
cd ./skill_opt_framework
pip install -r requirements.txt
```

Set environment variables:

```bash
export ANTHROPIC_API_KEY="<your_key>"
# Set this only if your provider requires a custom Anthropic-compatible endpoint:
# export ANTHROPIC_BASE_URL="https://<provider-endpoint>"
```

Or use a local secrets file (no need to export every time):

```bash
cd ./skill_opt_framework
cp llm_secrets.example.json .llm_secrets.json
# Edit .llm_secrets.json with your real key and endpoint
```

Use API adapter in config:

```json
"llm_command": "python3 ./skill_opt_framework/tools/anthropic_api_llm.py --model MiniMax-M2.7 --max-tokens 2500 --temperature 0.2 --secrets-file ./skill_opt_framework/.llm_secrets.json"
```

You can also tune via env vars used by adapter:

- `MINIMAX_MODEL`
- `LLM_MAX_TOKENS`
- `LLM_TEMPERATURE`
- `LLM_SYSTEM_PROMPT`

Adapter resolution priority:

1. CLI args (`--api-key`, `--base-url`)
2. Environment vars (`ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, also supports `MINIMAX_API_KEY`, `MINIMAX_BASE_URL`)
3. Secrets JSON file (`--secrets-file`)

## Case I Setup Example

For your current setup (`case_i.json` + `batch_generate.py` + `eval_glm_i.log`):

- `workspace_root`: `./claude_gen_code`
- `task_case_json`: `./claude_gen_code/case_i.json`
- `generate_command`: `python3 batch_generate.py`
- `evaluate_command`: `python3 dynamic_eval_i.py`
- `generated_output_dir_template`: `gpt_ci`
- `evaluation_log_path_template`: `./claude_gen_code/eval_glm_i.log`

With this setup, the optimizer can automatically classify reasons such as `SYNTAX_UNTERMINATED_STRING`, `ENV_PORT_IN_USE`, and `NOT_TRIGGERED`, then generate more targeted skill revisions.

## Output

- `output/runs.jsonl`: raw run-level logs
- `output/failures.jsonl`: extracted failed records
- `output/iterations.jsonl`: each iteration summary
- `output/final_summary.json`: final best skill info
- `output/report/`: markdown and chart report assets
