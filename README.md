# HEPToolBench

HEPToolBench is a deterministic benchmark for evaluating language models on
high-energy-physics software workflows.

The repository contains the frozen HEPToolBench v1.2 task suite, model runners,
artifact-based validators, deterministic scorers, result-analysis utilities,
and reproducibility metadata used for the benchmark paper.

HEPToolBench is the benchmark repository only. The companion agent software is
maintained separately in the `HEPLocalAgent` repository.

## Main features

- 31 benchmark tasks covering MadGraph, Pythia8, Delphes, structured debugging,
  artifact inspection, scans, plotting, and reproducibility checks.
- Deterministic scoring without an LLM judge.
- Freeform and schema-described response formats.
- Local Ollama runners and provider/API runners.
- Per-task partial scores and strict binary pass indicators.
- Resumable runs with separate output directories.
- Utilities for producing long-form CSV files, score matrices, summaries, and
  paper figures.

## Prerequisites

For local Ollama evaluation you need:

- Git
- Bash
- Python 3
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

## Quick start

Clone the repository and prepare the benchmark launcher:

```bash
git clone https://github.com/AadarshSingh0/HEPToolBench.git
cd HEPToolBench
chmod +x install.sh run_benchmark.sh
./install.sh
```

Launch the guided benchmark interface:

```bash
./run_benchmark.sh
```

The setup command does not install or start Ollama and does not download model
weights.

## Examples

Run every installed Ollama model on the full 31-task suite:

```bash
./run_benchmark.sh \
  --models all-installed \
  --suite full31 \
  --yes
```

Use a separately hosted Ollama service:

```bash
./run_benchmark.sh \
  --ollama-host http://HOST:11434 \
  --models llama3:8b qwen3:8b \
  --suite full31 \
  --yes
```

Resume an interrupted run:

A resumed run preserves the Ollama serving settings stored in its manifest. Start a new run ID to change serving settings.

```bash
./run_benchmark.sh --resume RUN_ID
```

See:

```text
local_llm_benchmark/docs/RUN_LOCAL_MODELS.md
```

for the complete local-model evaluation guide.

## Output layout

Each benchmark invocation receives a separate run directory. Typical generated
files include:

```text
local_llm_benchmark/runs/<run_id>/individual_scores.csv
local_llm_benchmark/runs/<run_id>/score_matrix.csv
local_llm_benchmark/runs/<run_id>/summary_by_model.csv
local_llm_benchmark/runs/<run_id>/summary_by_task.csv
local_llm_benchmark/results/all_runs_long.csv
```

Existing runs are not overwritten, and interrupted runs can be resumed.

## Repository structure

```text
local_llm_benchmark/
├── tasks/              Task families, prompts, inputs, and deterministic scorers
├── runners/            Ollama and provider-specific model runners
├── scripts/            Evaluation, auditing, and aggregation utilities
├── tests/              Offline transport and generation-setting tests
├── docs/               Usage, suite, and transport documentation
├── submissions/        Runtime model artifacts; normally untracked
├── runs/               Isolated benchmark invocations; ignored by Git
└── results/            Curated public results and generated summaries
```

## Reproducibility and privacy

Generated event files, local model weights, secrets, temporary environments,
runtime caches, and machine-local logs should not be committed.

For the public release, retained historical result metadata has machine-specific
absolute filesystem roots and private network addresses normalized to
repository-relative paths or explicit placeholders. Model responses, scores,
pass/fail values, task identifiers, timestamps, and stability statistics are
not changed by this publication-only normalization.

## Companion software

The deterministic local workflow agent described in the companion paper is
distributed separately as `HEPLocalAgent`.

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
