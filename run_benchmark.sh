#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_ROOT="${ROOT}/local_llm_benchmark"
PYTHON="${PYTHON:-python3}"

command -v "${PYTHON}" >/dev/null 2>&1 || {
    echo "ERROR: Python executable not found: ${PYTHON}"
    echo "Set PYTHON=/path/to/python if Python is not available as python3."
    exit 1
}

[[ -f "${BENCHMARK_ROOT}/run_benchmark.py" ]] || {
    echo "ERROR: Benchmark entry point is missing:"
    echo "  ${BENCHMARK_ROOT}/run_benchmark.py"
    exit 1
}

cd "${BENCHMARK_ROOT}"
exec "${PYTHON}" run_benchmark.py "$@"
