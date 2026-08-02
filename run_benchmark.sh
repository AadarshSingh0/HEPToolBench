#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_ROOT="${ROOT}/local_llm_benchmark"

if [[ -x "${ROOT}/local_hep_agent/.venv/bin/python" ]]; then
    PYTHON="${ROOT}/local_hep_agent/.venv/bin/python"
else
    PYTHON="${PYTHON:-python3}"
fi

cd "${BENCHMARK_ROOT}"
exec "${PYTHON}" run_benchmark.py "$@"
