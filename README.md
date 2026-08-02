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
├── tasks/              Benchmark task definitions
├── scorers/            Deterministic artifact scorers
├── runners/            Local and provider-specific runners
├── scripts/            Evaluation and aggregation utilities
├── tests/              Benchmark tests
├── docs/               Usage and reproducibility documentation
├── metadata/           Environment and run metadata
└── results/            Curated benchmark result artifacts
```

## Reproducibility and privacy

Generated event files, local model weights, secrets, temporary environments,
runtime caches, and machine-local logs should not be committed.

Some archived benchmark results and manifests retain historical host metadata
as provenance. Private network addresses appearing in those frozen records are
not public Internet endpoints.

## Companion software

The deterministic local workflow agent described in the companion paper is
distributed separately as `HEPLocalAgent`.
