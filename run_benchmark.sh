#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_ROOT="${ROOT}/local_llm_benchmark"
PYTHON="${PYTHON:-python3}"

command -v "${PYTHON}" >/dev/null 2>&1 || {
    echo "ERROR: Python executable not found: ${PYTHON}"
    exit 1
}

[[ -f "${BENCHMARK_ROOT}/run_benchmark.py" ]] || {
    echo "ERROR: Benchmark entry point is missing:"
    echo "  ${BENCHMARK_ROOT}/run_benchmark.py"
    exit 1
}

show_generation_help() {
    cat <<'HELP'

Additional Ollama generation controls
-------------------------------------

--num-ctx N
    Context window passed to the benchmark runner.
    HEPToolBench default: 4096.

--think VALUE
    Ollama thinking control.
    VALUE: auto | true | false | low | medium | high | max
    Default: auto (leave the model/Ollama default unchanged).

--temperature VALUE
    Sampling temperature, for example 0, 0.2, or 0.8.
    Default: auto (model/Ollama default).

--seed VALUE
    Integer random seed.
    Default: auto (model/Ollama default).

--num-predict VALUE
    Maximum generation-token budget.
    Default: auto (model/Ollama default).

Examples:

  ./run_benchmark.sh \
    --models qwen3:8b \
    --suite full31 \
    --yes

  ./run_benchmark.sh \
    --models qwen3:8b \
    --suite full31 \
    --num-ctx 8192 \
    --think false \
    --temperature 0.2 \
    --seed 0 \
    --num-predict 4096 \
    --yes

Local Ollama generation uses HTTP /api/generate.
HEPToolBench does not capture generations through `ollama run`.
HELP
}

for arg in "$@"; do
    if [[ "$arg" == "-h" || "$arg" == "--help" ]]; then
        cd "${BENCHMARK_ROOT}"
        "${PYTHON}" run_benchmark.py --help
        show_generation_help
        exit 0
    fi
done

PASSTHRU=()
PASSTHRU_COUNT=0

require_value() {
    local option="$1"
    local value="${2:-}"
    if [[ -z "$value" ]]; then
        echo "ERROR: ${option} requires a value." >&2
        exit 2
    fi
}

while (($#)); do
    case "$1" in
        --think)
            require_value "$1" "${2:-}"
            export HEPTOOLBENCH_OLLAMA_THINK="$2"
            shift 2
            ;;
        --think=*)
            export HEPTOOLBENCH_OLLAMA_THINK="${1#*=}"
            shift
            ;;

        --temperature)
            require_value "$1" "${2:-}"
            export HEPTOOLBENCH_OLLAMA_TEMPERATURE="$2"
            shift 2
            ;;
        --temperature=*)
            export HEPTOOLBENCH_OLLAMA_TEMPERATURE="${1#*=}"
            shift
            ;;

        --seed)
            require_value "$1" "${2:-}"
            export HEPTOOLBENCH_OLLAMA_SEED="$2"
            shift 2
            ;;
        --seed=*)
            export HEPTOOLBENCH_OLLAMA_SEED="${1#*=}"
            shift
            ;;

        --num-predict)
            require_value "$1" "${2:-}"
            export HEPTOOLBENCH_OLLAMA_NUM_PREDICT="$2"
            shift 2
            ;;
        --num-predict=*)
            export HEPTOOLBENCH_OLLAMA_NUM_PREDICT="${1#*=}"
            shift
            ;;

        *)
            PASSTHRU+=("$1")
            PASSTHRU_COUNT=$((PASSTHRU_COUNT + 1))
            shift
            ;;
    esac
done

cd "${BENCHMARK_ROOT}"

set +e
if ((PASSTHRU_COUNT)); then
    "${PYTHON}" run_benchmark.py "${PASSTHRU[@]}"
else
    "${PYTHON}" run_benchmark.py
fi
RC=$?
set -e

if [[ "$RC" != "0" ]]; then
    cat >&2 <<'HINT'

HEPToolBench did not complete cleanly.

If this looks like a model-serving or generation problem, try:

  output ended with done_reason="length" or is incomplete:
      increase --num-ctx and/or --num-predict

  reasoning consumed the response budget:
      try --think false

  model rejects the think setting:
      use --think auto

  Ollama reports memory/OOM pressure:
      reduce --num-ctx

  generation is unstable or malformed:
      try a lower --temperature

  you need repeatability while diagnosing behavior:
      set an explicit --seed

Generation overrides affect benchmark comparability. Report non-default
serving settings with published scores.

Run:
  ./run_benchmark.sh --help

to see the available controls.
HINT
fi

exit "$RC"
