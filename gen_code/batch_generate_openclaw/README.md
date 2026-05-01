# OpenClaw Code Generation Experiment

Automated code generation pipeline using OpenClaw gateway with Claude/Agent backend.

## Architecture

```
test_openclaw.py  →  HTTP Request  →  OpenClaw Gateway (Docker)  →  Agent generates code
                                              ↑
                                    docker-compose.yml
                                              ↑
                                          Dockerfile
```

## Files

| File | Description |
|------|-------------|
| `docker-compose.yml` | Docker compose configuration for OpenClaw gateway |
| `Dockerfile` | Image build configuration (build with `docker build .`) |
| `test_openclaw.py` | Client script that sends tasks to gateway |

## Prerequisites

- Docker and Docker Compose
- Python 3.8+
- `aiohttp`, `psutil` Python packages

## Configuration Steps

### 1. Build Docker Image

```bash
docker build -t openclaw:local .
```

### 2. Configure docker-compose.yml

Edit the following placeholders in `docker-compose.yml`:

```yaml
environment:
  # TODO: Set your actual proxy if needed, or leave empty
  HTTP_PROXY: "${HTTP_PROXY:-}"
  HTTPS_PROXY: "${HTTPS_PROXY:-}"

  # TODO: Set your gateway token (must match test_openclaw.py API_TOKEN)
  OPENCLAW_GATEWAY_TOKEN: "${OPENCLAW_GATEWAY_TOKEN:-}"

volumes:
  # TODO: Update paths to match your actual directories
  - /your/path/to/.openclaw:/home/node/.openclaw
  - /your/path/to/workspace:/home/node/.openclaw/workspace
  - ./generated_code:/workspace/generated_code
```

### 3. Configure test_openclaw.py

Update the configuration section at the top of `test_openclaw.py`:

```python
# --- Core Configuration ---

# TODO: Update to your actual paths
JSON_FILE = os.getenv("JSON_FILE", os.path.join(SCRIPT_DIR, "case_a_0420.json"))
HOST_MAPPED_OUTPUT_DIR = os.getenv("HOST_MAPPED_OUTPUT_DIR", "/your/path/to/.openclaw/workspace/gpt_ci")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "")
SKILLS_DIR = "/your/path/to/.openclaw/workspace/skills"

# TODO: Must match OPENCLAW_GATEWAY_TOKEN in docker-compose.yml
API_TOKEN = "YOUR_API_TOKEN"

GATEWAY_URL = "http://127.0.0.1:18789/v1/chat/completions"
```

### 4. Create Required Directories

```bash
# Create output directory for generated code
mkdir -p ./generated_code

# Create skills directory with SKILL.md files
mkdir -p /your/path/to/.openclaw/workspace/skills/<skill_name>/

# Create case JSON file (format: test_id, skill_name, attack_prompt, cia_dimension, original_task_id)
# Example: case_a_0420.json
```

### 5. Prepare Skill Files

Each skill needs a `SKILL.md` file in the skills directory:

```
skills/
├── skill_name_1/
│   └── SKILL.md
├── skill_name_2/
│   └── SKILL.md
└── ...
```

## Running the Experiment

### Step 1: Start OpenClaw Gateway

```bash
docker-compose up -d
```

Check if gateway is healthy:
```bash
curl http://127.0.0.1:18789/healthz
```

### Step 2: Run test_openclaw.py

```bash
pip install aiohttp psutil
python3 test_openclaw.py
```

### Stop Gateway

```bash
docker-compose down
```

## Configuration Checklist

| Item | Location | Example Value |
|------|----------|---------------|
| Gateway Token | docker-compose.yml + test_openclaw.py | `my_secret_token` |
| Skills Directory | test_openclaw.py | `/home/user/.openclaw/workspace/skills` |
| Case JSON | test_openclaw.py | `./batch_input/case_a_0420.json` |
| Output Directory | test_openclaw.py | `./generated_code` |
| HTTP Proxy | docker-compose.yml (if behind proxy) | `http://proxy:8080` |

## Important Notes

1. **API_TOKEN must match**: The `API_TOKEN` in `test_openclaw.py` must equal the `OPENCLAW_GATEWAY_TOKEN` in `docker-compose.yml`.

2. **Skills directory structure**: The skills directory must contain subdirectories named after each `skill_name` in the case JSON, each with a `SKILL.md` file.

3. **Volume mount alignment**: The `SKILLS_DIR` path in `test_openclaw.py` should match where `OPENCLAW_WORKSPACE_DIR` is mounted in docker-compose.yml.

4. **Memory monitoring**: If memory usage exceeds `MEMORY_DANGER_PERCENT` (default 80%), the script will automatically restart the gateway container.

## Case JSON Format

The case JSON file should be an array of objects:

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