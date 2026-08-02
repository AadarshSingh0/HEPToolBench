#!/usr/bin/env python3
import json
from collections import defaultdict
from pathlib import Path

MODELS = [
    "llama3:8b",
    "qwen3:8b",
    "qwen2.5-coder:14b",
    "qwen3-coder-next:Q4_K_M",
    "gemma4:31b",
    "qwen3.5:35b",
    "qwen3-next:80b",
    "gemma4:26b",
    "mistral-small3.2:24b",
    "devstral:24b",
    "granite4:32b-a9b-h",
    "qwen3.5:27b",
    "gpt-oss:120b",
    "llama3.3:70b",
    "deepseek-r1:70b",
    "ministral-3:14b",
    "phi4-reasoning:plus",
]

TASKS = [
    "mg_basic_001",
    "mg_basic_002",
    "mg_basic_003",
    "mg_debug_001",
    "mg_debug_002",
    "mg_debug_003",
    "mg_structured_001",
    "mg_structured_002",
    "mg_structured_003",
    "mg_runcard_004",
    "mg_runcard_structured_004",
    "mg_workflow_005",
    "mg_workflow_structured_005",
    "mg_parse_006",
    "mg_parse_007",
    "mg_parse_008",
    "mg_parse_009",
    "pythia_config_010",
    "delphes_objects_011",
    "lhe_sanity_012",
    "cutflow_diagnosis_013",
    "scan_plan_014",
    "param_card_patch_015",
    "scan_results_016",
    "scan_recovery_017",
    "benchmark_recommendation_018",
    "plot_data_019",
    "repro_audit_020",
]

records = defaultdict(dict)

for path in Path("results").glob("*.json"):
    try:
        data = json.loads(path.read_text(errors="ignore"))
    except Exception:
        continue

    model = data.get("model")
    task = data.get("task_id")

    if model not in MODELS or task not in TASKS:
        continue

    if "score" not in data or "passed" not in data:
        continue

    records[model][task] = data

print(
    f"{'model':42s} "
    f"{'done':>7s} "
    f"{'pass':>7s} "
    f"{'mean':>8s} "
    f"{'next missing':30s}"
)
print("-" * 102)

for model in MODELS:
    vals = records[model]

    done = len(vals)
    passed = sum(bool(x.get("passed")) for x in vals.values())

    scores = [
        float(x.get("score", 0) or 0)
        for x in vals.values()
    ]

    mean = sum(scores) / len(scores) if scores else 0.0

    missing = [task for task in TASKS if task not in vals]
    next_missing = missing[0] if missing else "COMPLETE"

    print(
        f"{model:42s} "
        f"{done:2d}/28 "
        f"{passed:7d} "
        f"{mean:8.4f} "
        f"{next_missing:30s}"
    )
