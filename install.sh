#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MODE="both"
AGENT_ARGS=()
AGENT_ARG_COUNT=0

usage() {
    cat <<'EOF'
HEPToolBench installer

Usage:
  ./install.sh [--both|--agent-only|--benchmark-only] [agent installer options]

Examples:
  ./install.sh
  ./install.sh --benchmark-only
  ./install.sh --agent-only --full
  ./install.sh --agent-only --install-system-deps \
    --ollama-host http://OTHER-COMPUTER:11434
  ./install.sh --both --install-ollama --pull-model
EOF
}

while (($#)); do
    case "$1" in
        --both) MODE="both" ;;
        --agent-only) MODE="agent" ;;
        --benchmark-only) MODE="benchmark" ;;
        -h|--help) usage; exit 0 ;;
        *)
            AGENT_ARGS+=("$1")
            AGENT_ARG_COUNT=$((AGENT_ARG_COUNT + 1))
            ;;
    esac
    shift
done

install_benchmark() {
    echo
    echo "============================================================"
    echo "SETTING UP LOCAL LLM BENCHMARK"
    echo "============================================================"

    command -v python3 >/dev/null 2>&1 || {
        echo "ERROR: python3 is required."
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

    python3 -m py_compile \
        "${ROOT}/local_llm_benchmark/run_benchmark.py" \
        "${ROOT}/local_llm_benchmark/scripts/build_universal_csv.py" \
        "${ROOT}/local_llm_benchmark/runners/run_ollama_task.py"

    echo "Benchmark interface: ready"
    echo "Run it with: ./run_benchmark.sh"
}

install_agent() {
    local -a agent_command=(
        "${ROOT}/local_hep_agent/install.sh"
    )

    echo
    echo "============================================================"
    echo "SETTING UP LOCAL HEP AGENT"
    echo "============================================================"

    chmod +x \
        "${ROOT}/uninstall.sh" \
        "${ROOT}/local_hep_agent/install.sh" \
        "${ROOT}/local_hep_agent/run_agent.sh" \
        "${ROOT}/local_hep_agent/uninstall.sh" \
        "${ROOT}/local_hep_agent/scripts/uninstall_local_hep_agent.sh"

    if (( AGENT_ARG_COUNT > 0 )); then
        agent_command+=("${AGENT_ARGS[@]}")
    fi

    "${agent_command[@]}"
}

case "${MODE}" in
    benchmark)
        if (( AGENT_ARG_COUNT > 0 )); then
            echo "WARNING: agent installer options are ignored in benchmark-only mode."
        fi
        install_benchmark
        ;;
    agent)
        install_agent
        ;;
    both)
        install_benchmark
        install_agent
        ;;
esac

echo
echo "============================================================"
echo "INSTALLATION COMPLETE"
echo "============================================================"
echo "Agent:     ./run_agent.sh"
echo "Benchmark: ./run_benchmark.sh"
echo "Uninstall: ./uninstall.sh"
