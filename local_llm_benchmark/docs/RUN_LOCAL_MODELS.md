# Running local models on HEPToolBench

This guide is for users who can run a few terminal commands but do not want to
edit Python files.

## Prerequisites

For local Ollama evaluation you need:

- Git
- Bash
- Python 3.10 or newer
- Ollama installed locally, or access to a remote Ollama server
- At least one Ollama model for local runs

The local runner uses only the Python standard library; no extra pip packages are required.

On Linux, install Ollama with the official installer:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3:8b
ollama list
```

For macOS and Windows, use the official Ollama download page: https://ollama.com/download.

## Install the benchmark interface

From the repository root:

```bash
chmod +x install.sh run_benchmark.sh
./install.sh
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

The saved Ollama serving configuration is authoritative during resume. Changing num_ctx, think, temperature, seed, or num_predict requires a new run ID.

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

## Ollama generation controls

HEPToolBench sends local-model requests directly to Ollama through the
non-streaming HTTP `/api/generate` endpoint. It does not capture model
generations from `ollama run`.

For a newly installed Ollama model, the normal command is:

```bash
./run_benchmark.sh \
  --models MODEL_NAME \
  --suite full31 \
  --yes
```

The default serving configuration is:

- `num_ctx = 4096`
- `think = auto`
- `temperature = auto`
- `seed = auto`
- `num_predict = auto`

Here, `auto` means HEPToolBench does not override the corresponding
Ollama/model default. The 4096-token context window is the explicit
HEPToolBench default and can be changed by the user.

Advanced users can override the serving configuration:

```bash
./run_benchmark.sh \
  --models MODEL_NAME \
  --suite full31 \
  --num-ctx 8192 \
  --think false \
  --temperature 0.2 \
  --seed 7 \
  --num-predict 2048 \
  --yes
```

Available controls are:

- `--num-ctx N`: context window.
- `--think VALUE`: `auto`, `true`, `false`, `low`, `medium`, `high`, or `max`.
- `--temperature VALUE`: sampling temperature.
- `--seed VALUE`: integer random seed.
- `--num-predict VALUE`: maximum generation-token budget.

The selected serving configuration is stored in `run_manifest.json` under
`ollama_generation_settings`. Each attempt also stores the exact HTTP request
and response metadata in `ollama_http_metadata.json`.

If generation ends because of length, try increasing `--num-ctx` or
`--num-predict`. If reasoning consumes the response budget, try
`--think false` when supported. Reduce `--num-ctx` for memory pressure,
and consider a lower `--temperature` or an explicit `--seed` when
investigating unstable output.

Generation settings affect model behavior, so non-default serving settings
should be reported when benchmark scores are published or compared.
