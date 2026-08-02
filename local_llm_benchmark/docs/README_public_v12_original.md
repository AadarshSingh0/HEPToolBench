# HEPToolBench benchmark

This folder contains the public HEPToolBench benchmark suite used for the paper evaluation.

The frozen suite contains **31 tasks**:

- **28 de-leaked main tasks** covering MadGraph process cards, run cards, workflow construction, log parsing, Pythia/Delphes/LHE sanity checks, scan planning, result summarization, plot-data construction, and reproducibility auditing.
- **3 structured-debug extension tasks** requiring machine-readable JSON repair patches for broken MadGraph process cards.

## Folder layout

```text
tasks/          benchmark tasks, prompts, inputs, expected outputs, and deterministic scorers
runners/        local/API model runners and the submission evaluator
scripts/        analysis and batch-running utilities
docs/           usage notes
paper_results/  paper-ready result tables, when included
```

## Scoring policy

Each task has a deterministic scorer in `tests/score.py`. The scorer returns both:

- `score`: a partial-credit numerical score;
- `passed`: a task-specific binary acceptance label.

For JSON-output tasks, invalid JSON is treated as an invalid machine-readable artifact. Once the required artifact is parseable, task-specific semantic checks assign partial credit.

## Evaluate an existing submission

```bash
python runners/evaluate_submission.py   --task mg_structured_001   --submission path/to/submission.json
```

## Run one local Ollama model

```bash
export OLLAMA_HOST=http://127.0.0.1:11434  # optional
python runners/run_ollama_task.py --model llama3:8b --task plot_data_019
```

Outputs are written to `submissions/` and `results/`. These folders are ignored by git.

## Run API models

Set the relevant API key environment variables privately, then use the provider-specific runners or the batch script:

```bash
export GEMINI_API_KEY=...
export GITHUB_TOKEN=...
export MISTRAL_API_KEY=...
export SARVAM_API_KEY=...

export TASK_SET=all31
bash scripts/run_v12_api_frontier_all.sh .
```

The API model list is controlled by `api_model_matrix.tsv`.

## Summarize results

```bash
python scripts/summarize_results.py --results results --out paper_results/generated
```

## Version

See `VERSION` for the frozen benchmark version used in the paper.
