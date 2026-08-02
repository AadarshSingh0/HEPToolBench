#!/usr/bin/env python3

import csv
import json
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

GROUPS = {
    "direct": [
        "mg_basic_001",
        "mg_basic_002",
        "mg_basic_003",
        "mg_debug_001",
        "mg_debug_002",
        "mg_debug_003",
        "mg_runcard_004",
        "mg_workflow_005",
    ],
    "structured": [
        "mg_structured_001",
        "mg_structured_002",
        "mg_structured_003",
        "mg_runcard_structured_004",
        "mg_workflow_structured_005",
    ],
    "parsing_config": [
        "mg_parse_006",
        "mg_parse_007",
        "mg_parse_008",
        "mg_parse_009",
        "pythia_config_010",
        "delphes_objects_011",
        "lhe_sanity_012",
    ],
    "analysis_recovery": [
        "cutflow_diagnosis_013",
        "scan_plan_014",
        "param_card_patch_015",
        "scan_results_016",
        "scan_recovery_017",
        "benchmark_recommendation_018",
        "plot_data_019",
        "repro_audit_020",
    ],
}

# Choose the newest clean result if duplicate model/task files exist.
records = {}

for path in Path("results").rglob("*.json"):
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

    try:
        score = float(data.get("score", 0) or 0)
    except Exception:
        continue

    key = (model, task)
    candidate = {
        "model": model,
        "task": task,
        "score": score,
        "passed": bool(data.get("passed")),
        "failure_modes": data.get("failure_modes") or [],
        "path": str(path),
        "mtime": path.stat().st_mtime,
    }

    if key not in records or candidate["mtime"] > records[key]["mtime"]:
        records[key] = candidate


def group_metrics(model, tasks):
    vals = [
        records[(model, task)]
        for task in tasks
        if (model, task) in records
    ]

    if not vals:
        return 0, 0, 0.0

    passed = sum(x["passed"] for x in vals)
    mean = sum(x["score"] for x in vals) / len(vals)

    return len(vals), passed, mean


summary = []

for model in MODELS:
    vals = [
        records[(model, task)]
        for task in TASKS
        if (model, task) in records
    ]

    done = len(vals)
    passed = sum(x["passed"] for x in vals)
    mean = sum(x["score"] for x in vals) / done if done else 0.0
    missing = [task for task in TASKS if (model, task) not in records]

    row = {
        "model": model,
        "done": done,
        "passed": passed,
        "pass_rate": passed / done if done else 0.0,
        "mean_score": mean,
        "missing_count": len(missing),
        "missing_tasks": ";".join(missing),
    }

    for group_name, group_tasks in GROUPS.items():
        g_done, g_passed, g_mean = group_metrics(model, group_tasks)
        row[f"{group_name}_done"] = g_done
        row[f"{group_name}_passed"] = g_passed
        row[f"{group_name}_mean"] = g_mean

    summary.append(row)

summary.sort(
    key=lambda x: (
        x["done"] == 28,
        x["passed"],
        x["mean_score"],
    ),
    reverse=True,
)

outdir = Path("compiled_results")
outdir.mkdir(exist_ok=True)

summary_path = outdir / "full28_model_summary.csv"

fieldnames = [
    "model",
    "done",
    "passed",
    "pass_rate",
    "mean_score",
    "direct_done",
    "direct_passed",
    "direct_mean",
    "structured_done",
    "structured_passed",
    "structured_mean",
    "parsing_config_done",
    "parsing_config_passed",
    "parsing_config_mean",
    "analysis_recovery_done",
    "analysis_recovery_passed",
    "analysis_recovery_mean",
    "missing_count",
    "missing_tasks",
]

with summary_path.open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(summary)

matrix_path = outdir / "full28_task_matrix.csv"

with matrix_path.open("w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "model",
        "task",
        "score",
        "passed",
        "failure_modes",
        "result_file",
    ])

    for model in MODELS:
        for task in TASKS:
            rec = records.get((model, task))

            if rec is None:
                writer.writerow([model, task, "", "", "MISSING", ""])
            else:
                writer.writerow([
                    model,
                    task,
                    rec["score"],
                    rec["passed"],
                    ";".join(map(str, rec["failure_modes"])),
                    rec["path"],
                ])

print(
    f"{'model':40s} "
    f"{'done':>7s} "
    f"{'pass':>6s} "
    f"{'mean':>8s} "
    f"{'direct':>10s} "
    f"{'structured':>12s}"
)
print("-" * 91)

for row in summary:
    print(
        f"{row['model']:40s} "
        f"{row['done']:2d}/28 "
        f"{row['passed']:6d} "
        f"{row['mean_score']:8.4f} "
        f"{row['direct_passed']:2d}/{row['direct_done']:<2d} "
        f"{row['structured_passed']:3d}/{row['structured_done']:<2d}"
    )

print()
print("Incomplete models:")

incomplete = [row for row in summary if row["done"] != 28]

if not incomplete:
    print("None — all models have 28/28 clean scored tasks.")
else:
    for row in incomplete:
        print(
            row["model"],
            f"{row['done']}/28",
            "missing:",
            row["missing_tasks"],
        )

print()
print("Saved:", summary_path)
print("Saved:", matrix_path)
