# HEPToolBench local-model benchmark

HEPToolBench v1.2 contains 31 deterministic benchmark tasks:

- 28 tasks in the main suite;
- 3 structured-debug extension tasks.

Each task follows the same reproducible structure:

```text
prompt + task inputs -> model output -> deterministic scorer -> result JSON
```

## Easiest way to run it

From the repository root:

```bash
./run_benchmark.sh
```

The guided menu detects models installed on the selected Ollama server and asks
which models, suite, and repeat count to use.

A new isolated run folder is created every time:

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

The cumulative long-form table is rebuilt automatically:

```text
results/all_runs_long.csv
```

Every CSV row corresponds to one model, task, repeat, and benchmark invocation.
Failed evaluations and timeouts are retained. Missing evaluations are not
silently converted into zero scores.

## Noninteractive examples

```bash
../run_benchmark.sh \
  --models llama3:8b qwen3:8b \
  --suite full31 \
  --repeats 1 \
  --yes
```

```bash
../run_benchmark.sh \
  --ollama-host http://HOST:11434 \
  --models all-installed \
  --suite main28 \
  --yes
```

```bash
../run_benchmark.sh \
  --models llama3:8b \
  --tasks mg_basic_001 mg_structured_001 \
  --yes
```

Resume after interruption:

```bash
../run_benchmark.sh --resume RUN_ID
```

## Advanced single-task runner

```bash
python3 runners/run_ollama_task.py \
  --task mg_basic_001 \
  --model llama3:8b \
  --output-root /tmp/heptoolbench_single_task
```

Both `--model MODEL` and `--models MODEL_A MODEL_B` are accepted.

## Rebuild CSV files manually

```bash
python3 scripts/build_universal_csv.py
```

See `docs/RUN_LOCAL_MODELS.md` for full details.
