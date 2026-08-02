#!/usr/bin/env python3

import csv
import json
import re
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

LOG_PATTERNS = [
    "logs/full28/*.log",
    "logs/repeat/*.log",
]

TIME_FORMAT = "%A %d %B %Y %I:%M:%S %p"


def parse_time(text):
    text = text.strip()

    # Remove a short terminal timezone label such as IST or UTC.
    parts = text.rsplit(" ", 1)
    if len(parts) == 2 and parts[1].isalpha() and len(parts[1]) <= 5:
        text = parts[0]

    return datetime.strptime(text, TIME_FORMAT)


starts = defaultdict(list)

for pattern in LOG_PATTERNS:
    for log_path in Path(".").glob(pattern):
        current = None

        for line in log_path.read_text(errors="ignore").splitlines():
            match = re.match(r"RUNNING:\s*(.*?)\s*->\s*(\S+)\s*$", line)

            if match:
                current = (match.group(1).strip(), match.group(2).strip())
                continue

            if current and line.startswith("TIME:"):
                try:
                    started = parse_time(line.split("TIME:", 1)[1])
                except Exception:
                    current = None
                    continue

                starts[current].append(started)
                current = None


# Keep the newest valid result for each model--task pair.
results = {}

for path in Path("results").glob("*.json"):
    try:
        data = json.loads(path.read_text(errors="ignore"))
    except Exception:
        continue

    model = data.get("model")
    task = data.get("task_id")

    if not model or not task:
        continue

    if "score" not in data or "passed" not in data:
        continue

    key = (model, task)

    candidate = {
        "model": model,
        "task": task,
        "score": float(data.get("score", 0) or 0),
        "passed": bool(data.get("passed")),
        "path": path,
        "mtime": path.stat().st_mtime,
    }

    if key not in results or candidate["mtime"] > results[key]["mtime"]:
        results[key] = candidate


runtime_rows = []

for key, result in results.items():
    model, task = key
    completed = datetime.fromtimestamp(result["mtime"])

    possible_starts = [
        start
        for start in starts.get(key, [])
        if start <= completed + timedelta(seconds=3)
    ]

    if not possible_starts:
        continue

    # Selecting the latest preceding start handles resumed runs correctly.
    started = max(possible_starts)
    elapsed = (completed - started).total_seconds()

    if elapsed < 0:
        continue

    runtime_rows.append({
        "model": model,
        "task": task,
        "start_time": started.isoformat(sep=" "),
        "completion_time": completed.isoformat(sep=" "),
        "elapsed_seconds": round(elapsed, 3),
        "score": result["score"],
        "passed": result["passed"],
        "result_file": str(result["path"]),
    })


runtime_rows.sort(key=lambda row: (row["model"], row["start_time"]))

outdir = Path("compiled_results")
outdir.mkdir(exist_ok=True)

task_csv = outdir / "task_runtime.csv"

with task_csv.open("w", newline="") as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=[
            "model",
            "task",
            "start_time",
            "completion_time",
            "elapsed_seconds",
            "score",
            "passed",
            "result_file",
        ],
    )
    writer.writeheader()
    writer.writerows(runtime_rows)


by_model = defaultdict(list)

for row in runtime_rows:
    by_model[row["model"]].append(row)


def percentile_90(values):
    if len(values) == 1:
        return values[0]

    return statistics.quantiles(
        values,
        n=10,
        method="inclusive",
    )[8]


summary = []

for model, rows in by_model.items():
    ordered = sorted(rows, key=lambda row: row["start_time"])
    durations = [row["elapsed_seconds"] for row in ordered]

    # The first generation normally includes model loading.
    warm_durations = durations[1:] if len(durations) > 1 else durations

    summary.append({
        "model": model,
        "timed_tasks": len(durations),
        "total_hours": sum(durations) / 3600.0,
        "mean_minutes": statistics.mean(durations) / 60.0,
        "median_minutes": statistics.median(durations) / 60.0,
        "warm_median_minutes": statistics.median(warm_durations) / 60.0,
        "p90_minutes": percentile_90(durations) / 60.0,
        "maximum_minutes": max(durations) / 60.0,
    })


summary.sort(key=lambda row: row["warm_median_minutes"])

summary_csv = outdir / "model_runtime_summary.csv"

with summary_csv.open("w", newline="") as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=[
            "model",
            "timed_tasks",
            "total_hours",
            "mean_minutes",
            "median_minutes",
            "warm_median_minutes",
            "p90_minutes",
            "maximum_minutes",
        ],
    )
    writer.writeheader()
    writer.writerows(summary)


print(
    f"{'model':40s} "
    f"{'N':>3s} "
    f"{'total h':>9s} "
    f"{'mean m':>9s} "
    f"{'median m':>10s} "
    f"{'warm med':>10s} "
    f"{'p90 m':>9s}"
)
print("-" * 99)

for row in summary:
    print(
        f"{row['model']:40s} "
        f"{row['timed_tasks']:3d} "
        f"{row['total_hours']:9.2f} "
        f"{row['mean_minutes']:9.2f} "
        f"{row['median_minutes']:10.2f} "
        f"{row['warm_median_minutes']:10.2f} "
        f"{row['p90_minutes']:9.2f}"
    )


def latex_escape(text):
    return (
        text.replace("\\", r"\textbackslash{}")
        .replace("_", r"\_")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("#", r"\#")
    )


table_dir = Path("tables")
table_dir.mkdir(exist_ok=True)

tex_path = table_dir / "local_runtime_summary.tex"

with tex_path.open("w") as handle:
    handle.write(r"""\begin{table*}[t]
\centering
\small
\caption{Local-model wall-clock timing. The warm median excludes the first
request for each model, which may include model-loading overhead.}
\label{tab:local-runtime-summary}
\begin{tabular}{lrrrrrr}
\toprule
Model & Timed tasks & Total [h] & Mean [min] & Median [min] &
Warm median [min] & P90 [min] \\
\midrule
""")

    for row in summary:
        model = latex_escape(row["model"])
        handle.write(
            rf"\texttt{{{model}}} & "
            rf"{row['timed_tasks']} & "
            rf"{row['total_hours']:.2f} & "
            rf"{row['mean_minutes']:.2f} & "
            rf"{row['median_minutes']:.2f} & "
            rf"{row['warm_median_minutes']:.2f} & "
            rf"{row['p90_minutes']:.2f} \\" + "\n"
        )

    handle.write(r"""\bottomrule
\end{tabular}
\end{table*}
""")


print()
print("Saved:", task_csv)
print("Saved:", summary_csv)
print("Saved:", tex_path)
