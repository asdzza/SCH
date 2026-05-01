# Skill Optimization Experiment

Iterative skill optimization via offline analysis and candidate generation.

## Entry Point

```bash
python3 run_iterative_opt_experiment.py
```

## Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--workspace` | `./workspace` | Root working directory |
| `--case-json` | `./case_i.json` | Case JSON with `skill_name` and `attack_prompt` |
| `--baseline-code-dir` | `./baseline_code` | Baseline generated code directory |
| `--base-skills-dir` | `./skills` | Base skill definitions (`skill_name/SKILL.md`) |
| `--rounds` | 5 | Number of optimization rounds |
| `--quality-regression-threshold` | 1.0 | Quality regression threshold for rollback |
| `--disable-champion-rollback` | false | Disable champion rollback |
| `--skill-opt-root` | `./skill_opt_framework` | Path to the optimization framework |
| `--llm-command` | (see below) | LLM command for analysis |

Default llm-command:
```
python3 ./skill_opt_framework/tools/anthropic_api_llm.py --model MiniMax-M2.7 --max-tokens 2500 --temperature 0.0 --secrets-file ./skill_opt_framework/.llm_secrets.json
```

## Prerequisites

1. **Install dependencies**:
   ```bash
   cd skill_opt_framework && pip install -r requirements.txt
   ```

2. **Configure API access** in `./skill_opt_framework/.llm_secrets.json`:
   ```json
   {
     "ANTHROPIC_API_KEY": "YOUR_API_KEY",
     "ANTHROPIC_BASE_URL": "https://api.minimaxi.com/anthropic"
   }
   ```

3. **Prepare case JSON** with fields: `test_id`, `skill_name`, `attack_prompt`, `cia_dimension`, `original_task_id`

## Workflow Per Round

1. **Generation**: Run `batch_generate_experiment.py` with current skills
2. **Evaluation**: Run `dynamic_eval_i.py` to evaluate generated code
3. **Offline Analysis**: Run `offline_analyze.py` via `skill_opt_framework` to analyze failures
4. **Skill Update**: Apply candidate skill revisions from offline analysis
5. **Champion Tracking**: Track best performing skill set; rollback if quality regresses

## Output Structure

```
<workspace>/opt_experiments/runs/<timestamp>/
├── baseline/
│   ├── code/              # Baseline generated code
│   ├── case_matched.json
│   └── eval.log
├── skills/
│   ├── round_0/           # Initial skills
│   ├── round_1/
│   └── ...
├── round_1/
│   ├── generated/         # Generated code this round
│   ├── eval.log
│   ├── generation.log
│   ├── offline_opt/       # Offline analysis output
│   └── offline_config.json
└── summary.json           # Final experiment summary
```

## Key Scripts

- `run_iterative_opt_experiment.py`: Main entry point for iterative optimization
- `skill_opt_framework/offline_analyze.py`: Analyzes failures and generates candidates
- `skill_opt_framework/generate_report.py`: Generates visualization reports