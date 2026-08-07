#!/usr/bin/env bash
set -uo pipefail

export OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"

# Large CPU/RAM models may need substantial time.
RUNNER_TIMEOUT="${RUNNER_TIMEOUT:-21000}"
SHELL_TIMEOUT="${SHELL_TIMEOUT:-21600}"
SLEEP_BETWEEN_TASKS="${SLEEP_BETWEEN_TASKS:-5}"
MAX_CONSECUTIVE_INFRA_FAILURES="${MAX_CONSECUTIVE_INFRA_FAILURES:-2}"

MODELS=(
  # Controls
  "llama3:8b"
  "qwen3:8b"
  "qwen2.5-coder:14b"

  # New candidate models
  "qwen3-coder-next:Q4_K_M"
  "gemma4:31b"
  "qwen3.5:35b"
  "qwen3-next:80b"
  "gemma4:26b"
  "mistral-small3.2:24b"
  "devstral:24b"
  "granite4:32b-a9b-h"
  "qwen3.5:27b"
  "gpt-oss:120b"
  "llama3.3:70b"
  "deepseek-r1:70b"
  "ministral-3:14b"
  "phi4-reasoning:plus"
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

mkdir -p results submissions logs/full28 metadata

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

bad_phrases = [
    "api error",
    "connection error",
    "connection refused",
    "timed out",
    "timeout error",
    "model not found",
    "failed to load model",
    "out of memory",
    "requires more system memory",
    "server error",
    "service unavailable",
]

for path in Path("results").glob("*.json"):
    try:
        text = path.read_text(errors="ignore")
        data = json.loads(text)
    except Exception:
        continue

    if data.get("model") != model:
        continue

    if data.get("task_id") != task:
        continue

    if "score" not in data or "passed" not in data:
        continue

    low = text.lower()

    if any(phrase in low for phrase in bad_phrases):
        continue

    # A semantic score of zero is still a valid benchmark result.
    sys.exit(0)

sys.exit(1)
PY
}

echo "============================================================"
echo "HEPToolBench full 28-task local evaluation"
echo "Started: $(date)"
echo "OLLAMA_HOST=$OLLAMA_HOST"
echo "Models: ${#MODELS[@]}"
echo "Tasks per model: ${#TASKS[@]}"
echo "Maximum generations: $((${#MODELS[@]} * ${#TASKS[@]}))"
echo "============================================================"

for model in "${MODELS[@]}"; do
  safe=$(
    echo "$model" |
      sed 's|/|_|g; s|:|_|g; s|\.|_|g'
  )

  log="logs/full28/${safe}.log"
  consecutive_infra_failures=0

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
      consecutive_infra_failures=0
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
      consecutive_infra_failures=0
      rm -f "$tmp"
      sleep "$SLEEP_BETWEEN_TASKS"
      continue
    fi

    consecutive_infra_failures=$((consecutive_infra_failures + 1))

    if [ "$rc" -eq 124 ]; then
      echo "[shell timeout] $model -> $task" | tee -a "$log"
    elif [ "$rc" -ne 0 ]; then
      echo "[runner error rc=$rc] $model -> $task" | tee -a "$log"
    else
      echo "[no clean result produced] $model -> $task" | tee -a "$log"
    fi

    if grep -qiE \
      "out of memory|requires more system memory|failed to load model|model not found|connection refused" \
      "$tmp"; then
      echo "[fatal model/infrastructure error]" | tee -a "$log"
      echo "[skip remaining tasks for $model]" | tee -a "$log"
      rm -f "$tmp"
      break
    fi

    rm -f "$tmp"

    if [ "$consecutive_infra_failures" -ge "$MAX_CONSECUTIVE_INFRA_FAILURES" ]; then
      echo "[too many consecutive infrastructure failures]" | tee -a "$log"
      echo "[skip remaining tasks for $model]" | tee -a "$log"
      break
    fi

    sleep "$SLEEP_BETWEEN_TASKS"
  done

  ollama stop "$model" >/dev/null 2>&1 || true
  sleep 10

  echo "FINISHED MODEL: $model" | tee -a "$log"
  echo "TIME: $(date)" | tee -a "$log"
done

echo "============================================================"
echo "FULL-28 EVALUATION FINISHED: $(date)"
echo "============================================================"
