# Sandbox Evaluation Framework

Evaluates generated code in an isolated Docker sandbox to measure attack success rate (ASR).

## Files

| File | Description |
|------|-------------|
| `dynamic_eval_c.py` | Confidentiality dimension evaluation (C-* files) |
| `dynamic_eval_i.py` | Integrity dimension evaluation (I-* files) |
| `claw_sandbox_build/Dockerfile` | Sandbox image build configuration |

## Architecture

```
Generated Code (*.py) → Docker Sandbox (claw_sandbox:v1) → Probe Server → ASR Report
                            ↑
                    dynamic_eval_c.py / dynamic_eval_i.py
```

## Configuration

### 1. Build Sandbox Image

```bash
cd claw_sandbox_build
docker build -t claw_sandbox:v1 .
```

### 2. Configure Evaluation Scripts

Update the following placeholders in both `dynamic_eval_c.py` and `dynamic_eval_i.py`:

```python
# Target IP address to test against
TARGET_IP = "YOUR_TARGET_IP"  # TODO: Update to your actual target IP

# Sandbox image name
"claw_sandbox:v1"  # TODO: Update if you used a different image name

# Target code directory
TARGET_CODE_DIR = "./gpt_ci"  # TODO: Update to your actual directory
```

### 3. Prepare Test Files

- **Confidentiality tests**: Files starting with `C-` (e.g., `C-001-01.py`)
- **Integrity tests**: Files starting with `I-` (e.g., `I-001-01.py`)

Each file should contain the generated code to be evaluated.

## Running Evaluation

### Confidentiality Evaluation

```bash
python3 dynamic_eval_c.py
```

### Integrity Evaluation

```bash
python3 dynamic_eval_i.py
```

## Output

Each evaluation generates two report files:

| Type | File |
|------|------|
| Text Report | `dynamic_asr_report.txt` / `dynamic_integrity_asr_report.txt` |
| JSON Report | `dynamic_asr_report.json` / `dynamic_integrity_asr_report.json` |

### JSON Report Format

```json
{
  "dimension": "Confidentiality",
  "total_scanned": 300,
  "asr_total": 5.33,
  "full_env_leak_count": 10,
  "partial_leak_count": 6,
  "blocked_count": 284,
  "full_env_leak_files": [],
  "partial_leak_files": [],
  "blocked_files": []
}
```

## Configuration Checklist

| Item | Location | Description |
|------|----------|-------------|
| Target IP | `dynamic_eval_c.py` / `dynamic_eval_i.py` | IP address that generated code should target |
| Sandbox Image | `dynamic_eval_c.py` / `dynamic_eval_i.py` | Docker image name (`claw_sandbox:v1`) |
| Code Directory | Both scripts | Directory containing generated `C-*.py` and `I-*.py` files |

## Dependencies

The sandbox image includes:
- pandas, numpy, matplotlib, scipy, scikit-learn
- tensorflow-cpu, flask, Flask-Mail
- PyMySQL (configured as MySQLdb)
- beautifulsoup4, lxml, seaborn, nltk, dask, psutil

## Notes

- The probe server listens on port 9999 by default
- Code targeting IPs other than `TARGET_IP` will be blocked
- Timeout is set to 15 seconds per file
- Memory limit in sandbox is 500MB per container