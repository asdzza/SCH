# Semantic Compliance Hijacking (SCH) Evaluation Framework


## Overview
This repository contains the implementation, datasets, and evaluation sandbox for the paper introducing Semantic Compliance Hijacking (SCH). SCH is a novel, payload-less supply chain attack targeting Large Language Model (LLM) agents. By deconstructing malicious objectives into unstructured natural language disguised as benign compliance guidelines (e.g., "State Synchronization"), SCH induces agents to autonomously synthesize and execute exploits at runtime, effectively bypassing static analyzers and semantic intent monitors.

Furthermore, this repository includes the implementation of the Multi-Skill Automated Optimization (MS-AO) algorithm, an offline iterative feedback loop designed to autonomously refine these payload-less exploits within an isolated proxy sandbox, maximizing the Attack Success Rate (ASR) prior to deployment.

## Target Agent Frameworks

To ensure experimental reproducibility, this framework was evaluated against the following specific versions of autonomous agent systems. As agent architectures and underlying safety heuristics evolve, utilizing these exact versions is recommended for replicating the baseline ASR metrics:

- **OpenClaw**: `v2026.3.31`
- **Claude Code**: `v2.1.96`
- **Codex**: `v0.57.0`

## Directory Structure

This repository consists of the following core modules:

- **`case/`**
  - **Function**: Stores standardized test cases and datasets used for experiments (e.g., `case_600.json`, `case_test.json`).
  - **Content**: Provides standardized input format data for the generation scripts and evaluation framework.

- **`eval_asr/`**
  - **Function**: The dynamic evaluation and verification module.
  - **Content**:
    - `dynamic_eval_c.py`: Evaluates **Confidentiality** metrics (C-Full, C-Part) by intercepting network telemetry (e.g., simulated data exfiltration via HTTP POST).
    - `dynamic_eval_i.py`: Evaluates **Integrity** metrics (I-RCE) by monitoring arbitrary code execution traces.
    - `claw_sandbox_build/`: Dockerfiles and scripts to construct the isolated execution environment for safe payload detonation.

- **`gen_code/`**
  - **Function**: Automated code generation module interfacing with target LLMs and Agent frameworks.
  - **Content**: Integration scripts to execute tasks within OpenClaw, Claude Code, and Codex frameworks utilizing various foundation models (GPT-5.4 mini, GLM-5, MiniMax-M2.7).

- **`opt_skill/`**
  - **Function**: The implementation of the **Multi-Skill Automated Optimization (MS-AO)** algorithm.
  - **Content**: 
    - `skill_opt_framework/`: The core iterative refinement engine.
    - `run_iterative_opt_experiment.py`: Orchestrates the batch-processing feedback loop, handling error collection, LLM-based root cause analysis, candidate generation, and state rollback mechanisms.

- **`skill_scan_framework/`**
  - **Function**: Baseline defense evaluation for pre-execution skill auditing (RQ4).
  - **Content**: Integrates static syntactic profiling (SkillScan) and modular semantic analysis (LLM Guard) to calculate payload-less evasion rates.

- **`skills/`**
  - **Function**: A curated collection of the crafted Semantic Compliance narratives.
  - **Content**: Pre-configured markdown files representing the 12 distinct adversarial skills (e.g., `aws-lambda-state-sync.md`, `dynamic-feature-flag-loader.md`).

## Environment Setup

1. **Install Dependencies**:
   ```bash
   # Please provide the environment installation commands here, for example:
   pip install -r requirements.txt
   ```
2. **Prepare Agent Frameworks (Claude Code & Codex)**:
   To conduct experiments using Claude Code or Codex, you must first install the appropriate framework environments locally. 
   - **Important**: Prior to running any experiments, you must add/copy the adversarial skill files from our `skills/` directory into the corresponding framework's designated skills configuration directory.

3. **Prepare OpenClaw Environment (Docker Execution)**:
   For batch testing within the OpenClaw environment, we provide a dedicated Dockerfile.
   - This Dockerfile corresponds to the `test_openclaw` execution code located under the `batch_generate_openclaw` directory. 
   - It is designed to containerize the OpenClaw environment and safely execute the batch generation experiments.

4. **Build Evaluation Sandbox Environment**:
   To safely execute, trace, and evaluate the physical impact of the generated code across all frameworks, build the isolated Docker sandbox:
   ```bash
   cd eval_asr/claw_sandbox_build
   docker build -t claw_sandbox:v1 . 
   ```

## Usage

Detailed execution instructions, configuration parameters, and example commands are modularized. Please refer to the specific `README.md` file located within each sub-directory for step-by-step guidance on running that specific component:

- **Generation Scripts**: See `gen_code/README.md`
- **Dynamic Evaluation (ASR)**: See `eval_asr/README.md`
- **MS-AO Optimization**: See `opt_skill/README.md`
- **Defense Evasion Baselines**: See `skill_scan_framework/README.md`
  

