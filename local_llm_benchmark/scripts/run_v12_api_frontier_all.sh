#!/usr/bin/env bash
set -u

# Run from HEPToolBench-v1.2-work or pass repo path as first argument.
cd "${1:-$PWD}" || exit 1

mkdir -p logs results submissions audit/v12_api_frontier_all

TASK_SET="${TASK_SET:-all31}"       # all31, v1only, debug3
SLEEP_SEC="${SLEEP_SEC:-20}"       # raise to 60 if rate-limited
TIMEOUT_SEC="${TIMEOUT_SEC:-3600}"
MATRIX_FILE="${MATRIX_FILE:-api_model_matrix.tsv}"

RUN_LOG="logs/v12_api_frontier_all_${TASK_SET}_$(date +%Y%m%d_%H%M%S).log"
ERROR_LOG="audit/v12_api_frontier_all/run_errors_${TASK_SET}.csv"

V1_TASKS=(
mg_basic_001
mg_debug_001
mg_structured_001
mg_basic_002
mg_debug_002
mg_structured_002
mg_basic_003
mg_debug_003
mg_structured_003
mg_runcard_004
mg_runcard_structured_004
mg_workflow_005
mg_workflow_structured_005
mg_parse_006
mg_parse_007
mg_parse_008
mg_parse_009
pythia_config_010
delphes_objects_011
lhe_sanity_012
cutflow_diagnosis_013
scan_plan_014
param_card_patch_015
scan_results_016
scan_recovery_017
benchmark_recommendation_018
plot_data_019
repro_audit_020
)

DEBUG_TASKS=(
mg_debug_structured_001
mg_debug_structured_002
mg_debug_structured_003
)

case "$TASK_SET" in
  all31) TASKS=("${V1_TASKS[@]}" "${DEBUG_TASKS[@]}") ;;
  v1only) TASKS=("${V1_TASKS[@]}") ;;
  debug3) TASKS=("${DEBUG_TASKS[@]}") ;;
  *) echo "Unknown TASK_SET=$TASK_SET. Use all31, v1only, or debug3."; exit 2 ;;
esac

if [ ! -f "$MATRIX_FILE" ]; then
cat > "$MATRIX_FILE" <<'EOF'
# provider<TAB>runner<TAB>model
# Edit model IDs if your provider/runners use slightly different names.
gemini	runners/run_gemini_task.py	gemini-3.5-flash
gemini	runners/run_gemini_task.py	gemini-3.1-flash-lite
github	runners/run_github_task.py	openai/gpt-4.1
github	runners/run_github_task.py	openai/gpt-4.1-mini
github	runners/run_github_task.py	openai/gpt-4.1-nano
github	runners/run_github_task.py	meta/Llama-3.3-70B-Instruct
mistral	runners/run_mistral_task.py	mistral-large-2512
mistral	runners/run_mistral_task.py	magistral-medium-2509
mistral	runners/run_mistral_task.py	devstral-2512
mistral	runners/run_mistral_task.py	codestral-2508
mistral	runners/run_mistral_task.py	mistral-medium-2508
sarvam	runners/run_sarvam_task.py	sarvam-105b
EOF
  echo "[created default matrix] $MATRIX_FILE"
  echo "Please inspect/edit $MATRIX_FILE if needed, then rerun."
  exit 0
fi

safe_model_name () {
  python - "$1" <<'PY'
import re, sys
print(re.sub(r"[^A-Za-z0-9]+", "_", sys.argv[1]).strip("_"))
PY
}

resolve_runner () {
  local provider="$1"
  local requested="$2"
  local candidates=()

  candidates+=("$requested")
  case "$provider" in
    gemini)  candidates+=(runners/run_gemini_task.py runners/run_gemini_api_task.py runners/run_google_task.py runners/run_google_api_task.py) ;;
    github)  candidates+=(runners/run_github_task.py runners/run_github_api_task.py runners/run_gh_models_task.py) ;;
    mistral) candidates+=(runners/run_mistral_task.py runners/run_mistral_api_task.py) ;;
    sarvam)  candidates+=(runners/run_sarvam_task.py runners/run_sarvam_api_task.py) ;;
  esac

  local c
  for c in "${candidates[@]}"; do
    if [ -f "$c" ]; then
      echo "$c"
      return 0
    fi
  done
  return 1
}

provider_key_ok () {
  local provider="$1"
  case "$provider" in
    gemini)  [ -n "${GEMINI_API_KEY:-}" ] || [ -n "${GOOGLE_API_KEY:-}" ] ;;
    github)  [ -n "${GITHUB_TOKEN:-}" ] || [ -n "${GITHUB_API_KEY:-}" ] ;;
    mistral) [ -n "${MISTRAL_API_KEY:-}" ] ;;
    sarvam)  [ -n "${SARVAM_API_KEY:-}" ] ;;
    *) true ;;
  esac
}

echo "provider,model,task,status" > "$ERROR_LOG"

{
  echo "======================================"
  echo "HEPToolBench-v1.2 API frontier evaluation"
  echo "PWD: $(pwd)"
  echo "TASK_SET: $TASK_SET"
  echo "Tasks: ${#TASKS[@]}"
  echo "Matrix: $MATRIX_FILE"
  echo "Start: $(date)"
  echo "======================================"
} | tee -a "$RUN_LOG"

if [ -n "${GEMINI_API_KEY:-}${GOOGLE_API_KEY:-}${GITHUB_TOKEN:-}${GITHUB_API_KEY:-}${MISTRAL_API_KEY:-}${SARVAM_API_KEY:-}" ]; then
  echo "[keys] at least one API key env var is set; values hidden" | tee -a "$RUN_LOG"
else
  echo "[WARNING] no known API key env vars are set in this shell" | tee -a "$RUN_LOG"
fi

echo "[compile check]" | tee -a "$RUN_LOG"
python -m py_compile runners/*.py scripts/*.py tasks/*/*/tests/score.py 2>&1 | tee -a "$RUN_LOG"
if [ ${PIPESTATUS[0]} -ne 0 ]; then
  echo "[FATAL] compile check failed" | tee -a "$RUN_LOG"
  exit 1
fi

while IFS=$'\t' read -r PROVIDER REQUESTED_RUNNER MODEL REST; do
  # skip blank/comment lines
  [ -z "${PROVIDER:-}" ] && continue
  case "$PROVIDER" in \#*) continue ;; esac
  [ -z "${MODEL:-}" ] && continue

  if ! provider_key_ok "$PROVIDER"; then
    echo "[SKIP PROVIDER] missing API key for provider=$PROVIDER model=$MODEL" | tee -a "$RUN_LOG"
    continue
  fi

  RUNNER="$(resolve_runner "$PROVIDER" "$REQUESTED_RUNNER" || true)"
  if [ -z "$RUNNER" ]; then
    echo "[SKIP MODEL] runner missing for provider=$PROVIDER requested=$REQUESTED_RUNNER model=$MODEL" | tee -a "$RUN_LOG"
    echo "$PROVIDER,$MODEL,ALL,missing_runner" >> "$ERROR_LOG"
    continue
  fi

  SAFE="$(safe_model_name "$MODEL")"

  echo | tee -a "$RUN_LOG"
  echo "######################################" | tee -a "$RUN_LOG"
  echo "PROVIDER: $PROVIDER" | tee -a "$RUN_LOG"
  echo "RUNNER:   $RUNNER" | tee -a "$RUN_LOG"
  echo "MODEL:    $MODEL" | tee -a "$RUN_LOG"
  echo "TIME:     $(date)" | tee -a "$RUN_LOG"
  echo "######################################" | tee -a "$RUN_LOG"

  for TASK in "${TASKS[@]}"; do
    RESULT_FILE="results/${SAFE}_${TASK}.json"

    echo | tee -a "$RUN_LOG"
    echo "======================================" | tee -a "$RUN_LOG"
    echo "Running provider=$PROVIDER model=$MODEL task=$TASK" | tee -a "$RUN_LOG"
    echo "Time: $(date)" | tee -a "$RUN_LOG"
    echo "======================================" | tee -a "$RUN_LOG"

    if [ -f "$RESULT_FILE" ]; then
      echo "[SKIP] existing result: $RESULT_FILE" | tee -a "$RUN_LOG"
      continue
    fi

    timeout "$TIMEOUT_SEC" python "$RUNNER" \
      --model "$MODEL" \
      --task "$TASK" 2>&1 | tee -a "$RUN_LOG"

    STATUS=${PIPESTATUS[0]}

    if [ $STATUS -ne 0 ]; then
      echo "[ERROR] provider=$PROVIDER model=$MODEL task=$TASK status=$STATUS" | tee -a "$RUN_LOG"
      echo "$PROVIDER,$MODEL,$TASK,$STATUS" >> "$ERROR_LOG"
    fi

    sleep "$SLEEP_SEC"
  done

  echo | tee -a "$RUN_LOG"
  echo "[SUMMARY after $PROVIDER / $MODEL]" | tee -a "$RUN_LOG"
  python scripts/summarize_results.py \
    --results results \
    --out audit/v12_api_frontier_all/current_summary_${TASK_SET} 2>&1 | tee -a "$RUN_LOG"

done < "$MATRIX_FILE"

echo | tee -a "$RUN_LOG"
echo "======================================" | tee -a "$RUN_LOG"
echo "FINAL SUMMARY" | tee -a "$RUN_LOG"
echo "End: $(date)" | tee -a "$RUN_LOG"
echo "======================================" | tee -a "$RUN_LOG"

python scripts/summarize_results.py \
  --results results \
  --out audit/v12_api_frontier_all/final_summary_${TASK_SET} 2>&1 | tee -a "$RUN_LOG"

echo "Done. Main log: $RUN_LOG" | tee -a "$RUN_LOG"
