#!/usr/bin/env python3

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

RUNS = {
    "r01": Path.home() / "Benchmark/HEPToolBench_local_final_full28_20260711_r01",
    "r02": Path.home() / "Benchmark/HEPToolBench_local_shortlist_full28_r02_clean",
    "r03": Path.home() / "Benchmark/HEPToolBench_local_shortlist_full28_r03_clean",
}

MODELS = [
    "gemma4:31b",
    "llama3.3:70b",
    "gemma4:26b",
    "qwen3-coder-next:Q4_K_M",
    "qwen2.5-coder:14b",
    "llama3:8b",
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

DIRECT_TASKS = {
    "mg_basic_001",
    "mg_basic_002",
    "mg_basic_003",
    "mg_debug_001",
    "mg_debug_002",
    "mg_debug_003",
    "mg_runcard_004",
    "mg_workflow_005",
}

STRUCTURED_TASKS = {
    "mg_structured_001",
    "mg_structured_002",
    "mg_structured_003",
    "mg_runcard_structured_004",
    "mg_workflow_structured_005",
}


def sample_std(values):
    return statistics.stdev(values) if len(values) > 1 else 0.0


def p90(values):
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]

    return statistics.quantiles(
        values,
        n=10,
        method="inclusive",
    )[8]


def newest_results(run_dir):
    records = {}

    for path in (run_dir / "results").glob("*.json"):
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

        key = (model, task)

        candidate = {
            "score": float(data.get("score", 0) or 0),
            "passed": bool(data.get("passed")),
            "failure_modes": data.get("failure_modes") or [],
            "path": str(path),
            "mtime": path.stat().st_mtime,
        }

        if key not in records or candidate["mtime"] > records[key]["mtime"]:
            records[key] = candidate

    return records


all_results = {}
repeat_rows = []

for repeat, run_dir in RUNS.items():
    records = newest_results(run_dir)
    all_results[repeat] = records

    for model in MODELS:
        vals = [
            records[(model, task)]
            for task in TASKS
            if (model, task) in records
        ]

        scores = [x["score"] for x in vals]
        passed = sum(x["passed"] for x in vals)

        direct_vals = [
            records[(model, task)]
            for task in DIRECT_TASKS
            if (model, task) in records
        ]

        structured_vals = [
            records[(model, task)]
            for task in STRUCTURED_TASKS
            if (model, task) in records
        ]

        repeat_rows.append({
            "repeat": repeat,
            "model": model,
            "done": len(vals),
            "passed": passed,
            "mean_score": statistics.mean(scores) if scores else 0.0,
            "direct_passed": sum(x["passed"] for x in direct_vals),
            "structured_passed": sum(x["passed"] for x in structured_vals),
        })


runtime_rows = []

for repeat, run_dir in RUNS.items():
    runtime_path = run_dir / "compiled_results/task_runtime.csv"

    if not runtime_path.exists():
        print(f"WARNING: missing runtime CSV: {runtime_path}")
        continue

    with runtime_path.open() as handle:
        reader = csv.DictReader(handle)

        rows = []

        for row in reader:
            model = row.get("model")
            task = row.get("task")

            if model not in MODELS or task not in TASKS:
                continue

            try:
                elapsed = float(row["elapsed_seconds"])
            except Exception:
                continue

            rows.append({
                "repeat": repeat,
                "model": model,
                "task": task,
                "start_time": row.get("start_time", ""),
                "elapsed_seconds": elapsed,
            })

        # Identify the first generation separately for every model and run.
        by_model = defaultdict(list)

        for row in rows:
            by_model[row["model"]].append(row)

        for model, model_rows in by_model.items():
            ordered = sorted(
                model_rows,
                key=lambda x: x["start_time"],
            )

            for index, row in enumerate(ordered):
                row["cold_start_task"] = index == 0
                runtime_rows.append(row)


summary_rows = []

for model in MODELS:
    model_repeats = [
        row
        for row in repeat_rows
        if row["model"] == model
    ]

    pass_counts = [row["passed"] for row in model_repeats]
    repeat_means = [row["mean_score"] for row in model_repeats]
    direct_counts = [row["direct_passed"] for row in model_repeats]
    structured_counts = [row["structured_passed"] for row in model_repeats]

    stable_3_of_3 = 0
    passed_2_of_3 = 0
    unstable_tasks = 0

    for task in TASKS:
        outcomes = []

        for repeat in RUNS:
            record = all_results[repeat].get((model, task))

            if record is not None:
                outcomes.append(bool(record["passed"]))

        pass_frequency = sum(outcomes)

        if len(outcomes) == 3:
            if pass_frequency == 3:
                stable_3_of_3 += 1
            if pass_frequency >= 2:
                passed_2_of_3 += 1
            if pass_frequency in (1, 2):
                unstable_tasks += 1

    model_times = [
        row["elapsed_seconds"]
        for row in runtime_rows
        if row["model"] == model
    ]

    warm_times = [
        row["elapsed_seconds"]
        for row in runtime_rows
        if row["model"] == model
        and not row["cold_start_task"]
    ]

    summary_rows.append({
        "model": model,
        "completed_repeats": len(model_repeats),
        "mean_passes": statistics.mean(pass_counts) if pass_counts else 0.0,
        "pass_std": sample_std(pass_counts),
        "minimum_passes": min(pass_counts) if pass_counts else 0,
        "maximum_passes": max(pass_counts) if pass_counts else 0,
        "mean_score": statistics.mean(repeat_means) if repeat_means else 0.0,
        "score_std": sample_std(repeat_means),
        "mean_direct_passes": statistics.mean(direct_counts) if direct_counts else 0.0,
        "mean_structured_passes": statistics.mean(structured_counts) if structured_counts else 0.0,
        "tasks_passed_3_of_3": stable_3_of_3,
        "tasks_passed_at_least_2_of_3": passed_2_of_3,
        "unstable_tasks": unstable_tasks,
        "timed_generations": len(model_times),
        "mean_latency_minutes": statistics.mean(model_times) / 60.0 if model_times else 0.0,
        "median_latency_minutes": statistics.median(model_times) / 60.0 if model_times else 0.0,
        "warm_median_minutes": statistics.median(warm_times) / 60.0 if warm_times else 0.0,
        "p90_latency_minutes": p90(model_times) / 60.0 if model_times else 0.0,
    })


summary_rows.sort(
    key=lambda row: (
        row["mean_passes"],
        row["mean_score"],
        -row["warm_median_minutes"],
    ),
    reverse=True,
)


outdir = Path("compiled_results")
outdir.mkdir(exist_ok=True)

repeat_csv = outdir / "per_repeat_model_results.csv"

with repeat_csv.open("w", newline="") as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=[
            "repeat",
            "model",
            "done",
            "passed",
            "mean_score",
            "direct_passed",
            "structured_passed",
        ],
    )
    writer.writeheader()
    writer.writerows(repeat_rows)


summary_csv = outdir / "three_repeat_model_summary.csv"

with summary_csv.open("w", newline="") as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=list(summary_rows[0].keys()),
    )
    writer.writeheader()
    writer.writerows(summary_rows)


task_rows = []

for model in MODELS:
    for task in TASKS:
        scores = []
        passes = []

        for repeat in RUNS:
            record = all_results[repeat].get((model, task))

            if record is None:
                continue

            scores.append(record["score"])
            passes.append(record["passed"])

        task_rows.append({
            "model": model,
            "task": task,
            "completed_repeats": len(scores),
            "mean_score": statistics.mean(scores) if scores else 0.0,
            "score_std": sample_std(scores),
            "pass_frequency": sum(passes),
            "pass_fraction": sum(passes) / len(passes) if passes else 0.0,
        })


task_csv = outdir / "three_repeat_task_stability.csv"

with task_csv.open("w", newline="") as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=list(task_rows[0].keys()),
    )
    writer.writeheader()
    writer.writerows(task_rows)


runtime_csv = outdir / "all_repeat_task_runtimes.csv"

with runtime_csv.open("w", newline="") as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=[
            "repeat",
            "model",
            "task",
            "start_time",
            "elapsed_seconds",
            "cold_start_task",
        ],
    )
    writer.writeheader()
    writer.writerows(runtime_rows)


print(
    f"{'model':38s} "
    f"{'passes':>13s} "
    f"{'score':>14s} "
    f"{'3/3':>5s} "
    f"{'>=2/3':>7s} "
    f"{'warm med':>10s} "
    f"{'p90':>8s}"
)
print("-" * 104)

for row in summary_rows:
    print(
        f"{row['model']:38s} "
        f"{row['mean_passes']:5.2f}"
        f"+/-{row['pass_std']:<5.2f} "
        f"{row['mean_score']:.4f}"
        f"+/-{row['score_std']:<7.4f} "
        f"{row['tasks_passed_3_of_3']:5d} "
        f"{row['tasks_passed_at_least_2_of_3']:7d} "
        f"{row['warm_median_minutes']:10.2f} "
        f"{row['p90_latency_minutes']:8.2f}"
    )

print()
print("Per-repeat completion:")

for row in repeat_rows:
    print(
        f"{row['repeat']:3s} "
        f"{row['model']:38s} "
        f"{row['done']:2d}/28 "
        f"passes={row['passed']:2d} "
        f"mean={row['mean_score']:.4f}"
    )

print()
print("Saved:", repeat_csv)
print("Saved:", summary_csv)
print("Saved:", task_csv)
print("Saved:", runtime_csv)
