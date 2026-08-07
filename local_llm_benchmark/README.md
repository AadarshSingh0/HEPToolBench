# HEPToolBench benchmark implementation

This directory contains the frozen HEPToolBench v1.2 benchmark.

The suite contains 31 deterministic tasks:

- 28 tasks in the `main28` benchmark suite;
- 3 structured-debug extension tasks;
- all 31 tasks together form `full31`.

HEPToolBench evaluates model-generated HEP workflow artifacts with
deterministic task-specific scorers. No LLM judge is used.

## Normal way to run the benchmark

From the repository root:

```bash
./install.sh
./run_benchmark.sh
```

The guided launcher can select Ollama models, choose `main28` or `full31`,
set repeat counts, configure generation settings, and create an isolated run
directory.

## Example noninteractive run

```bash
./run_benchmark.sh --models llama3:8b qwen3:8b --suite full31 --repeats 1 --yes
```

## Remote Ollama example

```bash
./run_benchmark.sh --ollama-host http://HOST:11434 --models qwen3:8b --suite full31 --yes
```

## Small task-level check

```bash
./run_benchmark.sh --models llama3:8b --tasks mg_basic_001 mg_structured_001 --repeats 1 --yes
```

## Resume an interrupted run

A resumed run preserves its recorded Ollama serving configuration. Start a new run ID to change serving settings.

```bash
./run_benchmark.sh --resume RUN_ID
```

Completed model-task-repeat evaluations are retained rather than rerun.

## Generated run layout

Each benchmark invocation creates:

```text
runs/<run_id>/
├── run_manifest.json
├── results/
├── submissions/
├── raw_responses/
├── individual_scores.csv
├── score_matrix.csv
├── summary_by_model.csv
└── summary_by_task.csv
```

Runtime runs are ignored by Git.

The cumulative local table is:

```text
results/all_runs_long.csv
```

Failed evaluations and timeouts remain explicit records. Missing evaluations
are not silently converted into zero scores.

## Ollama evaluation transport

Local Ollama generations use the non-streaming HTTP `/api/generate` endpoint.
The normal public workflow does not capture generations through `ollama run`.

Supported serving controls include:

- `--num-ctx`
- `--think`
- `--temperature`
- `--seed`
- `--num-predict`

See `docs/RUN_LOCAL_MODELS.md` and `docs/OLLAMA_HTTP_TRANSPORT.md`.

## Important directories

- `tasks/` - benchmark task families and deterministic scorers.
- `runners/` - Ollama, API, and submission-evaluation runners.
- `scripts/` - aggregation, audit, and batch utilities.
- `docs/` - user and transport documentation.
- `tests/` - offline transport and generation-setting tests.
- `runs/` - generated isolated benchmark runs.
- `submissions/` - generated model artifacts.
- `results/` - curated public research results and generated summaries.

For the full directory map, see `FOLDER_GUIDE.txt`.
