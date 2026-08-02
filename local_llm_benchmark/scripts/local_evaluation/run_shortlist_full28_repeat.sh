#!/usr/bin/env bash
set -uo pipefail

export OLLAMA_HOST="${OLLAMA_HOST:-http://10.42.106.85:11434}"

RUNNER_TIMEOUT="${RUNNER_TIMEOUT:-21000}"
SHELL_TIMEOUT="${SHELL_TIMEOUT:-21600}"
SLEEP_BETWEEN_TASKS="${SLEEP_BETWEEN_TASKS:-5}"

MODELS=(
  "gemma4:31b"
  "llama3.3:70b"
  "gemma4:26b"
  "qwen3-coder-next:Q4_K_M"
  "qwen2.5-coder:14b"
  "llama3:8b"
)

TASKS=(
  "mg_basic_001"
  "mg_basic_002"
  "mg_basic_003"
  "mg_debug_001"
  "mg_debug_002"
  "mg_debug_003"
  "mg_structured_001"
  "mg_structured_002"
  "mg_structured_003"
  "mg_runcard_004"
  "mg_runcard_structured_004"
  "mg_workflow_005"
  "mg_workflow_structured_005"
  "mg_parse_006"
  "mg_parse_007"
  "mg_parse_008"
  "mg_parse_009"
  "pythia_config_010"
  "delphes_objects_011"
  "lhe_sanity_012"
  "cutflow_diagnosis_013"
  "scan_plan_014"
  "param_card_patch_015"
  "scan_results_016"
  "scan_recovery_017"
  "benchmark_recommendation_018"
  "plot_data_019"
  "repro_audit_020"
)

mkdir -p results submissions logs/repeat metadata

# Prevent another accidental run with missing benchmark input logs.
REQUIRED_INPUTS=(
  "tasks/mg_parse/task_006_mg_log_summary_json/input/mg_run_summary.log"
  "tasks/mg_parse/task_007_mg_failure_diagnosis_json/input/mg_failed_run.log"
)

for input_file in "${REQUIRED_INPUTS[@]}"; do
  if [ ! -f "$input_file" ]; then
    echo "FATAL: required benchmark input is missing:"
    echo "$input_file"
    exit 20
  fi
done

model_is_installed () {
  local model="$1"

  ollama list |
    awk 'NR > 1 && NF > 0 {print $1}' |
    grep -Fxq "$model"
}

has_valid_result () {
  local model="$1"
  local task="$2"

  python - "$model" "$task" <<'PY'
import json
import sys
from pathlib import Path

model = sys.argv[1]
task = sys.argv[2]

for path in Path("results").glob("*.json"):
    try:
        data = json.loads(path.read_text(errors="ignore"))
    except Exception:
        continue

    if data.get("model") != model:
        continue

    if data.get("task_id") != task:
        continue

    if "score" not in data or "passed" not in data:
        continue

    # A semantic failure, including score=0, is still a valid benchmark result.
    sys.exit(0)

sys.exit(1)
PY
}

echo "============================================================"
echo "HEPToolBench shortlisted-model full-28 repeat"
echo "Directory: $(pwd)"
echo "Started: $(date)"
echo "OLLAMA_HOST=$OLLAMA_HOST"
echo "Models: ${#MODELS[@]}"
echo "Tasks per model: ${#TASKS[@]}"
echo "Maximum generations: $((${#MODELS[@]} * ${#TASKS[@]}))"
echo "============================================================"

for model in "${MODELS[@]}"; do
  safe=$(echo "$model" | sed 's|/|_|g; s|:|_|g; s|\.|_|g')
  log="logs/repeat/${safe}.log"

  echo "============================================================" | tee -a "$log"
  echo "MODEL: $model" | tee -a "$log"
  echo "START: $(date)" | tee -a "$log"
  echo "============================================================" | tee -a "$log"

  if ! model_is_installed "$model"; then
    echo "[missing model] $model" | tee -a "$log"
    echo "[skip model]" | tee -a "$log"
    continue
  fi

  for task in "${TASKS[@]}"; do
    if has_valid_result "$model" "$task"; then
      echo "[skip existing valid] $model -> $task" | tee -a "$log"
      continue
    fi

    echo "------------------------------------------------------------" | tee -a "$log"
    echo "RUNNING: $model -> $task" | tee -a "$log"
    echo "TIME: $(date)" | tee -a "$log"

    tmp=$(mktemp)

    timeout "$SHELL_TIMEOUT" \
      python runners/run_ollama_task2.py \
        --task "$task" \
        --models "$model" \
        --timeout "$RUNNER_TIMEOUT" \
        --repeats 1 2>&1 |
      tee "$tmp" |
      tee -a "$log"

    rc=${PIPESTATUS[0]}

    if has_valid_result "$model" "$task"; then
      echo "[saved valid] $model -> $task" | tee -a "$log"
    elif [ "$rc" -eq 124 ]; then
      echo "[shell timeout] $model -> $task" | tee -a "$log"
    elif [ "$rc" -ne 0 ]; then
      echo "[runner error rc=$rc] $model -> $task" | tee -a "$log"
    else
      echo "[no valid result produced] $model -> $task" | tee -a "$log"
    fi

    rm -f "$tmp"
    sleep "$SLEEP_BETWEEN_TASKS"
  done

  ollama stop "$model" >/dev/null 2>&1 || true
  sleep 10

  echo "FINISHED MODEL: $model" | tee -a "$log"
  echo "TIME: $(date)" | tee -a "$log"
done

echo "============================================================"
echo "REPEAT FINISHED: $(date)"
echo "============================================================"
