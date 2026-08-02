#!/usr/bin/env bash
set -u

cd "${1:-$HOME/Benchmark/HEPToolBench-v1.2-work}" || exit 1

echo "[PWD] $(pwd)"
echo

echo "[API-like runner files]"
find runners -maxdepth 1 -type f \
  \( -iname '*gemini*' -o -iname '*github*' -o -iname '*mistral*' -o -iname '*sarvam*' -o -iname '*api*' \) \
  -printf '%p\n' | sort || true

echo

echo "[Runner help first lines, if present]"
for r in \
  runners/run_gemini_task.py runners/run_gemini_api_task.py \
  runners/run_github_task.py runners/run_github_api_task.py \
  runners/run_mistral_task.py runners/run_mistral_api_task.py \
  runners/run_sarvam_task.py runners/run_sarvam_api_task.py
  do
    if [ -f "$r" ]; then
      echo "---------------- $r --help ----------------"
      python "$r" --help 2>&1 | head -40 || true
    fi
  done

echo

echo "[Expected secret env vars: present/missing only, values hidden]"
for k in GEMINI_API_KEY GOOGLE_API_KEY GITHUB_TOKEN GITHUB_API_KEY MISTRAL_API_KEY SARVAM_API_KEY; do
  if [ -n "${!k:-}" ]; then
    echo "$k=SET"
  else
    echo "$k=missing"
  fi
done

echo

echo "[Compile check]"
python -m py_compile runners/*.py scripts/*.py tasks/*/*/tests/score.py

echo

echo "[Gold check for v1.2 debug-structured tasks]"
python runners/evaluate_submission.py --task mg_debug_structured_001 --submission tasks/mg_debug_structured/task_001_drell_yan_repair_json/expected/repair.json | grep -E '"passed"|"score"|"task_id"' || true
python runners/evaluate_submission.py --task mg_debug_structured_002 --submission tasks/mg_debug_structured/task_002_top_pair_repair_json/expected/repair.json | grep -E '"passed"|"score"|"task_id"' || true
python runners/evaluate_submission.py --task mg_debug_structured_003 --submission tasks/mg_debug_structured/task_003_higgs_jet_repair_json/expected/repair.json | grep -E '"passed"|"score"|"task_id"' || true
