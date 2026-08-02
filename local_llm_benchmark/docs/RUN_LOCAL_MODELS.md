# Running local models on HEPToolBench

This guide is for users who can run a few terminal commands but do not want to
edit Python files.

## Install the benchmark interface

From the repository root:

```bash
chmod +x install.sh run_benchmark.sh
./install.sh --benchmark-only
```

The launcher itself uses only the Python standard library. Ollama must be
installed locally or reachable through `OLLAMA_HOST`.

## Guided run

```bash
./run_benchmark.sh
```

The menu shows the models returned by `ollama list`, then asks for the models,
task suite, repeat count, and confirmation.

## Generated files

Each invocation receives a unique `run_id` under:

```text
local_llm_benchmark/runs/<run_id>/
```

The main task-level file is `individual_scores.csv`. It contains one row per
model, task, and repeat, including score, pass/fail, strict pass when available,
failure modes, timeout status, runner-error status, wall time, and paths to the
scored JSON, submission, and unmodified model response.

The cumulative file is:

```text
local_llm_benchmark/results/all_runs_long.csv
```

A new benchmark invocation creates a new run directory and adds new rows to the
cumulative table. Earlier runs are not overwritten.

## Full noninteractive run

```bash
./run_benchmark.sh \
  --models llama3:8b qwen3:8b \
  --suite full31 \
  --repeats 1 \
  --timeout 1800 \
  --yes
```

Use every model visible to Ollama:

```bash
./run_benchmark.sh \
  --models all-installed \
  --suite full31 \
  --yes
```

## Remote Ollama server

```bash
./run_benchmark.sh \
  --ollama-host http://192.168.1.50:11434 \
  --models qwen3:8b \
  --suite full31 \
  --yes
```

## Resume an interrupted run

Pressing `Ctrl+C` stops safely after updating the manifest and CSV files.

```bash
./run_benchmark.sh --resume RUN_ID
```

Already valid model-task-repeat JSON files are skipped.

## Small test before a full run

```bash
./run_benchmark.sh \
  --models llama3:8b \
  --tasks mg_basic_001 mg_structured_001 \
  --repeats 1 \
  --timeout 900 \
  --yes
```

## Rebuild CSV files

The JSON files under `runs/` are the source of truth:

```bash
cd local_llm_benchmark
python3 scripts/build_universal_csv.py
```

Missing tasks remain absent. Failures and timeouts remain explicit rows.
