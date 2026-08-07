#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    cat <<'HELP'
HEPToolBench setup

Usage:
  ./install.sh
  ./install.sh --help

This prepares the benchmark interface and verifies its Python entry
files. It does not install or start Ollama and does not download models.
HELP
}

case "${1:-}" in
    "")
        ;;
    -h|--help)
        usage
        exit 0
        ;;
    *)
        echo "ERROR: Unknown argument: $1"
        usage
        exit 2
        ;;
esac

command -v python3 >/dev/null 2>&1 || {
    echo "ERROR: python3 is required."
    exit 1
}

python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" || {
    echo "ERROR: Python 3.10 or newer is required."
    exit 1
}

mkdir -p \
    "${ROOT}/local_llm_benchmark/runs" \
    "${ROOT}/local_llm_benchmark/results"

chmod +x \
    "${ROOT}/run_benchmark.sh" \
    "${ROOT}/local_llm_benchmark/run_benchmark.py" \
    "${ROOT}/local_llm_benchmark/scripts/build_universal_csv.py" \
    "${ROOT}/local_llm_benchmark/smoke_test_public.sh"

echo
echo "============================================================"
echo "HEPToolBench setup complete"
echo "============================================================"
echo
echo "Run the benchmark interface with:"
echo "  ./run_benchmark.sh"
