#!/usr/bin/env python3
"""Build per-run and cumulative long-form CSV files for HEPToolBench runs.

The source of truth is the scored JSON files under ``runs/<run_id>/results``.
Each row represents one model, one task, one repeat, and one benchmark run.
Failed tasks and timeouts remain explicit rows; missing tasks are not changed
into artificial zero-score rows.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = ROOT / "runs"
CUMULATIVE_CSV = ROOT / "results" / "all_runs_long.csv"

LONG_FIELDS = [
    "run_id",
    "started_at",
    "completed_at",
    "provider_or_runtime",
    "ollama_host",
    "model",
    "task_id",
    "task_partition",
    "repeat",
    "score",
    "passed",
    "strict_passed",
    "failure_modes",
    "timeout",
    "runner_error",
    "wall_time_seconds",
    "result_json",
    "submission_file",
    "raw_response_file",
]


def as_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n", ""}:
            return False
    if value is None:
        return default
    return bool(value)


def strict_passed_value(data: dict[str, Any]) -> str | bool:
    if "strict_passed" not in data:
        return ""
    return as_bool(data.get("strict_passed"))


def failure_modes(data: dict[str, Any]) -> list[str]:
    value = data.get("failure_modes") or []
    if isinstance(value, str):
        return [item for item in value.split(";") if item]
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def relative_path(value: str | Path | None) -> str:
    if not value:
        return ""
    path = Path(value)
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def parse_result(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict):
        return None

    required = ("run_id", "model", "task_id", "repeat", "score", "passed")
    if any(key not in data for key in required):
        return None

    try:
        score = float(data["score"])
        repeat = int(data["repeat"])
    except (TypeError, ValueError):
        return None

    failures = failure_modes(data)

    return {
        "run_id": str(data["run_id"]),
        "started_at": str(data.get("started_at", "")),
        "completed_at": str(data.get("completed_at", "")),
        "provider_or_runtime": str(data.get("provider_or_runtime", "local_ollama")),
        "ollama_host": str(data.get("ollama_host", "")),
        "model": str(data["model"]),
        "task_id": str(data["task_id"]),
        "task_partition": str(data.get("task_partition", "")),
        "repeat": repeat,
        "score": score,
        "passed": as_bool(data.get("passed")),
        "strict_passed": strict_passed_value(data),
        "failure_modes": ";".join(failures),
        "timeout": as_bool(
            data.get("timeout"),
            default=any("timeout" in item.lower() for item in failures),
        ),
        "runner_error": as_bool(data.get("runner_error")),
        "wall_time_seconds": data.get("wall_time_seconds", ""),
        "result_json": relative_path(path),
        "submission_file": relative_path(data.get("submission_file")),
        "raw_response_file": relative_path(data.get("raw_response_file")),
        "_mtime": path.stat().st_mtime,
    }


def discover_rows() -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    by_key: dict[tuple[str, str, str, int], dict[str, Any]] = {}

    if not RUNS_ROOT.exists():
        return [], warnings

    for path in sorted(RUNS_ROOT.glob("*/results/**/*.json")):
        row = parse_result(path)
        if row is None:
            continue

        key = (
            str(row["run_id"]),
            str(row["model"]),
            str(row["task_id"]),
            int(row["repeat"]),
        )
        previous = by_key.get(key)
        if previous is not None:
            warnings.append(f"duplicate result key {key}; keeping the newest JSON")
            if float(previous["_mtime"]) > float(row["_mtime"]):
                continue
        by_key[key] = row

    rows = list(by_key.values())
    rows.sort(
        key=lambda row: (
            str(row["run_id"]),
            str(row["model"]).lower(),
            int(row["repeat"]),
            str(row["task_id"]),
        )
    )
    for row in rows:
        row.pop("_mtime", None)
    return rows, warnings


def write_csv_atomic(
    path: Path,
    fieldnames: list[str],
    rows: Iterable[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        newline="",
        delete=False,
        dir=path.parent,
        prefix=f".{path.name}.",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        temporary = Path(handle.name)
    temporary.replace(path)


def write_score_matrix(path: Path, rows: list[dict[str, Any]]) -> None:
    tasks = sorted({str(row["task_id"]) for row in rows})
    model_repeats = sorted(
        {(str(row["model"]), int(row["repeat"])) for row in rows},
        key=lambda item: (item[0].lower(), item[1]),
    )
    by_key = {
        (str(row["model"]), int(row["repeat"]), str(row["task_id"])): row
        for row in rows
    }

    output: list[dict[str, Any]] = []
    for model, repeat in model_repeats:
        item: dict[str, Any] = {"model": model, "repeat": repeat}
        for task_id in tasks:
            result = by_key.get((model, repeat, task_id))
            item[task_id] = "" if result is None else result["score"]
        output.append(item)

    write_csv_atomic(path, ["model", "repeat", *tasks], output)


def write_model_summary(path: Path, rows: list[dict[str, Any]]) -> None:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["model"]), int(row["repeat"]))].append(row)

    output: list[dict[str, Any]] = []
    for (model, repeat), values in grouped.items():
        scores = [float(item["score"]) for item in values]
        passes = sum(bool(item["passed"]) for item in values)
        output.append(
            {
                "model": model,
                "repeat": repeat,
                "tasks_done": len(values),
                "tasks_passed": passes,
                "pass_rate": round(passes / len(values), 6),
                "mean_score": round(statistics.mean(scores), 6),
                "timeouts": sum(bool(item["timeout"]) for item in values),
                "runner_errors": sum(bool(item["runner_error"]) for item in values),
            }
        )

    output.sort(
        key=lambda row: (
            -float(row["pass_rate"]),
            -float(row["mean_score"]),
            str(row["model"]).lower(),
            int(row["repeat"]),
        )
    )
    fields = [
        "model",
        "repeat",
        "tasks_done",
        "tasks_passed",
        "pass_rate",
        "mean_score",
        "timeouts",
        "runner_errors",
    ]
    write_csv_atomic(path, fields, output)


def write_task_summary(path: Path, rows: list[dict[str, Any]]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["task_id"])].append(row)

    output: list[dict[str, Any]] = []
    for task_id, values in grouped.items():
        scores = [float(item["score"]) for item in values]
        passes = sum(bool(item["passed"]) for item in values)
        output.append(
            {
                "task_id": task_id,
                "evaluations": len(values),
                "passes": passes,
                "pass_rate": round(passes / len(values), 6),
                "mean_score": round(statistics.mean(scores), 6),
                "timeouts": sum(bool(item["timeout"]) for item in values),
                "runner_errors": sum(bool(item["runner_error"]) for item in values),
            }
        )

    output.sort(key=lambda row: str(row["task_id"]))
    fields = [
        "task_id",
        "evaluations",
        "passes",
        "pass_rate",
        "mean_score",
        "timeouts",
        "runner_errors",
    ]
    write_csv_atomic(path, fields, output)


def rebuild_outputs(*, quiet: bool = False) -> dict[str, int]:
    rows, warnings = discover_rows()
    write_csv_atomic(CUMULATIVE_CSV, LONG_FIELDS, rows)

    by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_run[str(row["run_id"])].append(row)

    for run_id, run_rows in by_run.items():
        run_dir = RUNS_ROOT / run_id
        write_csv_atomic(run_dir / "individual_scores.csv", LONG_FIELDS, run_rows)
        write_score_matrix(run_dir / "score_matrix.csv", run_rows)
        write_model_summary(run_dir / "summary_by_model.csv", run_rows)
        write_task_summary(run_dir / "summary_by_task.csv", run_rows)

    if not quiet:
        for warning in warnings:
            print(f"WARNING: {warning}")
        print(f"[done] rows: {len(rows)}")
        print(f"[done] runs: {len(by_run)}")
        print(f"[done] cumulative CSV: {CUMULATIVE_CSV}")

    return {"rows": len(rows), "runs": len(by_run), "warnings": len(warnings)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    rebuild_outputs(quiet=args.quiet)


if __name__ == "__main__":
    main()
