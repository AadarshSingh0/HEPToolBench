#!/usr/bin/env bash
# Non-destructive public smoke test.
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MODEL="${1:-llama3:8b}"
TMP_ROOT="$(mktemp -d -t heptoolbench_smoke_XXXXXX)"
trap 'rm -rf "${TMP_ROOT}"' EXIT

cd "${ROOT}"

echo "======================================"
echo "HEPToolBench public smoke test"
echo "Model: ${MODEL}"
echo "Temporary output: ${TMP_ROOT}"
echo "======================================"

echo
echo "[1/3] Compile check"
python3 -m py_compile \
    runners/*.py \
    scripts/*.py \
    run_benchmark.py \
    tasks/*/*/tests/score.py

echo
echo "[2/3] Easy JSON task"
timeout 900 python3 runners/run_ollama_task.py \
    --model "${MODEL}" \
    --task plot_data_019 \
    --output-root "${TMP_ROOT}"

echo
echo "[3/3] Structured MadGraph task"
timeout 900 python3 runners/run_ollama_task.py \
    --model "${MODEL}" \
    --task mg_structured_001 \
    --output-root "${TMP_ROOT}"

echo
echo "Smoke test completed successfully."
find "${TMP_ROOT}/results" -maxdepth 3 -type f -print | sort
