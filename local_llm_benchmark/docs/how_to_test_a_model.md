# How To Test A Model On HEPToolBench-v0

This document explains the manual testing loop for the first task.

## Task 001

Task ID:

```text
mg_basic_001
```

Task folder:

```text
tasks/mg_basic/task_001_drell_yan_template/
```

The model should read:

```text
prompt.md
input/proc_card_template.dat
```

and produce:

```text
proc_card.dat
```

## Manual Test Procedure

1. Give the contents of `prompt.md` and `input/proc_card_template.dat` to the model.
2. Ask the model to return only the completed `proc_card.dat`.
3. Save the model output as:

```text
submissions/<model_name>/mg_basic_001/proc_card.dat
```

4. Run:

```bash
python runners/evaluate_submission.py \
  --task mg_basic_001 \
  --submission submissions/<model_name>/mg_basic_001/proc_card.dat
```

Optional:

```bash
python runners/evaluate_submission.py \
  --task mg_basic_001 \
  --submission submissions/<model_name>/mg_basic_001/proc_card.dat \
  --output results/<model_name>_mg_basic_001.json
```

## What The Scorer Checks

The current scorer checks whether the answer:

- imports the Standard Model
- defines the proton beam
- uses the correct MadGraph process line: `generate p p > e+ e-`
- uses `output`
- uses `launch`
- sets `ebeam1` to `6500`
- sets `ebeam2` to `6500`

The scorer reports both:

- `score`: partial credit between 0 and 1
- `passed`: strict task success

For `mg_basic_001`, `passed` is true only if the model gives the correct process line and both correct beam energies:

```text
generate p p > e+ e-
set ebeam1 6500
set ebeam2 6500
```

It also flags common failures:

- compact `pp` syntax
- using `->` instead of `>`
- missing electron charges
- using 13 TeV for each beam instead of 6.5 TeV

## Important

This first scorer is static. It does not yet run MadGraph. That is intentional for the first task because we want the benchmark format to be stable before adding execution-dependent scoring.

## Automated Ollama Testing

If Ollama is installed, first edit the model list at the top of:

```text
runners/run_ollama_task.py
```

Example:

```python
MODELS_TO_TEST = [
    "deepseek-r1:8b",
    "llama3:8b",
    "qwen2.5:7b",
]
```

Use the exact names shown by:

```bash
ollama list
```

Then run:

```bash
cd HEPToolBench

python runners/run_ollama_task.py --task mg_basic_001
```

The script will create:

```text
submissions/<model_name>/mg_basic_001/proc_card.dat
results/<model_name>_mg_basic_001.json
results/leaderboard_mg_basic_001.csv
```

## Timeout Policy

Use a fixed timeout for the main benchmark. The default automated timeout is 180 seconds per model.

If a model times out, record it as a timeout in the main leaderboard. Do not replace it with a later 20-30 minute manual answer in the main score, because the benchmark is testing practical usability as well as correctness.

If you want, you can store a separate relaxed result with a different name, for example:

```text
results/model_name_mg_basic_001_relaxed.json
```

But keep the main leaderboard strict.

## Repeated Runs Policy

LLMs can give different answers across runs, even with similar prompts. For HEPToolBench, keep two modes separate:

1. Primary benchmark mode:

```text
temperature = 0 or the most deterministic setting available
one attempt per task
fixed timeout
```

This is the main leaderboard. It answers: "Can the model reliably solve the task on the first try under a practical time budget?"

2. Stability mode:

```text
run each model 3 or 5 times
report pass rate, mean score, and common failure modes
```

This is optional but useful. It answers: "Is the model consistently useful, or did it pass once by luck?"

Do not mix these two numbers. Report them separately:

```text
primary_pass: true/false
pass_rate_5: 3/5
mean_score_5: 0.72
```

To preview the exact prompt without running a model:

```bash
python runners/run_ollama_task.py --task mg_basic_001 --dry-run
```

You can still override the top-of-file list from the command line:

```bash
python runners/run_ollama_task.py \
  --task mg_basic_001 \
  --models deepseek-r1:8b llama3:8b
```

For stability testing, run each selected model multiple times:

```bash
python runners/run_ollama_task.py --task mg_basic_001 --repeats 3
```

This creates per-run outputs:

```text
submissions/<model_name>/mg_basic_001/run_1/proc_card.dat
submissions/<model_name>/mg_basic_001/run_2/proc_card.dat
submissions/<model_name>/mg_basic_001/run_3/proc_card.dat
```

and a stability summary:

```text
results/stability_mg_basic_001.csv
```

## Structured JSON Task

To test the scaffolded/agentic regime, run:

```bash
python runners/run_ollama_task.py --task mg_structured_001
```

In this task, the model should return only:

```json
{
  "model": "sm",
  "initial_state": ["p", "p"],
  "final_state": ["e+", "e-"],
  "beam_energy_gev": 6500,
  "output_dir": "DY_ee",
  "nevents": 10000
}
```

The scorer then uses a deterministic builder to assemble:

```text
import model sm
define p = g u c d s u~ c~ d~ s~
generate p p > e+ e-
output DY_ee
launch
set ebeam1 6500
set ebeam2 6500
```

The structured result reports two success flags:

- `passed`: JSON was extractable and the physics slots were correct.
- `strict_passed`: same as `passed`, but the model returned clean JSON only, with no markdown or explanation.

## Debug/Repair Task

To test whether a model can repair a broken MadGraph card, run:

```bash
python runners/run_ollama_task.py --task mg_debug_001
```

The model receives:

```text
import model sm
define p = g u c d s u~ c~ d~ s~
p p > e+ e-
output DY_ee
launch
set beam1 6500
set beam2 6500
```

The expected repaired card is:

```text
import model sm
define p = g u c d s u~ c~ d~ s~
generate p p > e+ e-
output DY_ee
launch
set ebeam1 6500
set ebeam2 6500
```

This is the third Drell-Yan regime:

```text
direct writer -> debug/repair -> structured JSON + builder
```
