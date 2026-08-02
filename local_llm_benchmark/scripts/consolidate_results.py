#!/usr/bin/env python3
"""Consolidate HEPToolBench result JSON files into CSV tables and SVG plots.

Examples:
    python scripts/consolidate_results.py \
      --inputs results

    python scripts/consolidate_results.py \
      --inputs ~/Benchmark/HEPToolBench/results_zips/*.zip \
      --output-dir analysis_outputs/run_001

The script reads per-model result JSON files, not only leaderboard CSVs. This
is intentional: per-model JSON files are the source of truth when a leaderboard
CSV is missing rows.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import statistics
import tempfile
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]


TASK_LABELS = {
    "mg_basic_001": "T1 direct DY",
    "mg_debug_001": "T1 debug DY",
    "mg_structured_001": "T1 structured DY",
    "mg_basic_002": "T2 direct ttbar",
    "mg_debug_002": "T2 debug ttbar",
    "mg_structured_002": "T2 structured ttbar",
    "mg_basic_003": "T3 direct h+j",
    "mg_debug_003": "T3 debug h+j",
    "mg_structured_003": "T3 structured h+j",
    "mg_runcard_004": "T4 direct run card",
    "mg_runcard_structured_004": "T4 structured run card",
    "mg_workflow_005": "T5 direct workflow",
    "mg_workflow_structured_005": "T5 structured workflow",
    "mg_parse_006": "T6 parse success log",
    "mg_parse_007": "T7 parse failure log",
    "mg_parse_008": "T8 parse + unit conversion",
    "mg_parse_009": "T9 validate event outputs",
    "pythia_config_010": "T10 validate Pythia config",
    "delphes_objects_011": "T11 validate Delphes objects",
    "lhe_sanity_012": "T12 validate LHE output",
    "cutflow_diagnosis_013": "T13 diagnose cutflow",
    "scan_plan_014": "T14 plan parameter scan",
    "param_card_patch_015": "T15 patch param card",
    "scan_results_016": "T16 summarize scan results",
    "scan_recovery_017": "T17 plan scan recovery",
    "benchmark_recommendation_018": "T18 recommend benchmark",
}


TASK_ORDER = list(TASK_LABELS)


def task_family(task_id: str) -> str:
    if task_id.startswith("mg_basic_"):
        return "direct_proc_card"
    if task_id.startswith("mg_debug_"):
        return "debug_repair"
    if task_id.startswith("mg_structured_"):
        return "structured_proc_card"
    if task_id == "mg_runcard_004":
        return "direct_run_card"
    if task_id == "mg_runcard_structured_004":
        return "structured_run_card"
    if task_id == "mg_workflow_005":
        return "direct_workflow"
    if task_id == "mg_workflow_structured_005":
        return "structured_workflow"
    if task_id.startswith("mg_parse_"):
        return "log_parsing"
    if task_id.startswith("pythia_config_"):
        return "pythia_config_validation"
    if task_id.startswith("delphes_objects_"):
        return "delphes_object_validation"
    if task_id.startswith("lhe_sanity_"):
        return "lhe_output_validation"
    if task_id.startswith("cutflow_diagnosis_"):
        return "cutflow_analysis"
    if task_id.startswith("scan_plan_"):
        return "parameter_scan_planning"
    if task_id.startswith("scan_results_"):
        return "scan_result_parsing"
    if task_id.startswith("scan_recovery_"):
        return "scan_recovery_planning"
    return "other"


def task_number(task_id: str) -> int:
    digits = "".join(ch for ch in task_id.rsplit("_", 1)[-1] if ch.isdigit())
    return int(digits) if digits else 999


@dataclass(frozen=True)
class ResultRow:
    source: str
    model: str
    task_id: str
    score: float
    passed: bool
    failure_modes: tuple[str, ...]
    repeat: str

    @property
    def timeout(self) -> bool:
        return any("timeout" in mode for mode in self.failure_modes)


def discover_json_files(inputs: list[Path]) -> Iterable[tuple[str, Path]]:
    for input_path in inputs:
        if input_path.is_dir():
            for json_path in sorted(input_path.rglob("*.json")):
                yield str(input_path), json_path
        elif input_path.is_file() and input_path.suffix.lower() == ".zip":
            with tempfile.TemporaryDirectory(prefix="heptoolbench_zip_") as tmp:
                tmp_path = Path(tmp)
                with zipfile.ZipFile(input_path) as zf:
                    zf.extractall(tmp_path)
                for json_path in sorted(tmp_path.rglob("*.json")):
                    yield str(input_path), json_path
        elif input_path.is_file() and input_path.suffix.lower() == ".json":
            yield str(input_path), input_path


def parse_result_json(source: str, json_path: Path) -> ResultRow | None:
    try:
        data = json.loads(json_path.read_text())
    except Exception:
        return None

    task_id = data.get("task_id")
    if not task_id:
        return None

    # Skip expected/reference JSONs and metadata files. Real result files have
    # model/score/passed or an Ollama failure record.
    if "score" not in data and "passed" not in data:
        return None

    model = data.get("model")
    if not model:
        # Fallback for older result files before model was stored in JSON.
        suffix = f"_{task_id}.json"
        name = json_path.name
        model = name[: -len(suffix)] if name.endswith(suffix) else json_path.stem

    failure_modes = data.get("failure_modes") or []
    if isinstance(failure_modes, str):
        failure_modes = [failure_modes]

    return ResultRow(
        source=source,
        model=str(model),
        task_id=str(task_id),
        score=float(data.get("score") or 0.0),
        passed=bool(data.get("passed")),
        failure_modes=tuple(str(mode) for mode in failure_modes),
        repeat=str(data.get("repeat", "")),
    )


def dedupe_rows(rows: list[ResultRow], *, include_source_in_key: bool) -> list[ResultRow]:
    """Keep the last row for identical model/task/repeat keys.

    Result archives sometimes contain copied results from earlier tasks. For a
    paper summary, the most useful default is global de-duplication by model and
    task. If source is included in the key, duplicate archives are preserved.
    """
    by_key: dict[tuple[str, ...], ResultRow] = {}
    for row in rows:
        if include_source_in_key:
            key = (row.source, row.model, row.task_id, row.repeat)
        else:
            key = (row.model, row.task_id, row.repeat)
        by_key[key] = row
    return list(by_key.values())


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def summarize_by_task(rows: list[ResultRow]) -> list[dict]:
    by_task: dict[str, list[ResultRow]] = defaultdict(list)
    for row in rows:
        by_task[row.task_id].append(row)

    summary = []
    for task_id, task_rows in by_task.items():
        n = len(task_rows)
        passes = sum(row.passed for row in task_rows)
        timeouts = sum(row.timeout for row in task_rows)
        scores = [row.score for row in task_rows]
        non_timeout = [row for row in task_rows if not row.timeout]
        non_timeout_passes = sum(row.passed for row in non_timeout)
        summary.append(
            {
                "task_id": task_id,
                "task_label": TASK_LABELS.get(task_id, task_id),
                "task_family": task_family(task_id),
                "n": n,
                "passes": passes,
                "pass_rate": round(passes / n, 4) if n else 0.0,
                "mean_score": round(statistics.mean(scores), 4) if scores else 0.0,
                "timeouts": timeouts,
                "timeout_rate": round(timeouts / n, 4) if n else 0.0,
                "non_timeout_n": len(non_timeout),
                "non_timeout_passes": non_timeout_passes,
                "non_timeout_pass_rate": round(non_timeout_passes / len(non_timeout), 4)
                if non_timeout
                else 0.0,
            }
        )
    return sorted(summary, key=lambda row: (task_number(row["task_id"]), TASK_ORDER.index(row["task_id"]) if row["task_id"] in TASK_ORDER else 999))


def summarize_by_model(rows: list[ResultRow]) -> list[dict]:
    by_model: dict[str, list[ResultRow]] = defaultdict(list)
    for row in rows:
        by_model[row.model].append(row)

    summary = []
    for model, model_rows in by_model.items():
        n = len(model_rows)
        passes = sum(row.passed for row in model_rows)
        timeouts = sum(row.timeout for row in model_rows)
        summary.append(
            {
                "model": model,
                "n": n,
                "passes": passes,
                "pass_rate": round(passes / n, 4) if n else 0.0,
                "mean_score": round(statistics.mean(row.score for row in model_rows), 4) if n else 0.0,
                "timeouts": timeouts,
                "timeout_rate": round(timeouts / n, 4) if n else 0.0,
            }
        )
    return sorted(summary, key=lambda row: (-row["pass_rate"], -row["mean_score"], row["model"]))


def summarize_by_family(rows: list[ResultRow]) -> list[dict]:
    by_family: dict[str, list[ResultRow]] = defaultdict(list)
    for row in rows:
        by_family[task_family(row.task_id)].append(row)

    summary = []
    for family, family_rows in by_family.items():
        n = len(family_rows)
        passes = sum(row.passed for row in family_rows)
        summary.append(
            {
                "task_family": family,
                "n": n,
                "passes": passes,
                "pass_rate": round(passes / n, 4) if n else 0.0,
                "mean_score": round(statistics.mean(row.score for row in family_rows), 4) if n else 0.0,
                "timeouts": sum(row.timeout for row in family_rows),
            }
        )
    return sorted(summary, key=lambda row: row["task_family"])


def summarize_failures(rows: list[ResultRow]) -> list[dict]:
    counts: Counter[tuple[str, str]] = Counter()
    for row in rows:
        for mode in row.failure_modes:
            counts[(row.task_id, mode)] += 1
    return [
        {
            "task_id": task_id,
            "task_label": TASK_LABELS.get(task_id, task_id),
            "failure_mode": mode,
            "count": count,
        }
        for (task_id, mode), count in sorted(counts.items(), key=lambda item: (task_number(item[0][0]), item[0][0], -item[1], item[0][1]))
    ]


def write_score_matrix(path: Path, rows: list[ResultRow]) -> None:
    tasks = sorted({row.task_id for row in rows}, key=lambda task_id: (task_number(task_id), TASK_ORDER.index(task_id) if task_id in TASK_ORDER else 999))
    models = sorted({row.model for row in rows})
    by_key = {(row.model, row.task_id): row for row in rows}
    matrix_rows = []
    for model in models:
        row = {"model": model}
        for task_id in tasks:
            result = by_key.get((model, task_id))
            row[task_id] = "" if result is None else result.score
        matrix_rows.append(row)
    write_csv(path, ["model", *tasks], matrix_rows)


def svg_bar_chart(
    path: Path,
    rows: list[dict],
    label_key: str,
    value_key: str,
    title: str,
    value_suffix: str = "",
    max_value: float | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    width = 1100
    row_h = 28
    top = 62
    left = 275
    right = 70
    bottom = 35
    height = top + bottom + row_h * max(1, len(rows))
    plot_w = width - left - right
    if max_value is None:
        max_value = max((float(row[value_key]) for row in rows), default=1.0)
        max_value = max(max_value, 1.0)

    palette = "#2563eb"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>text{font-family:Arial,Helvetica,sans-serif;font-size:13px}.title{font-size:20px;font-weight:700}.axis{fill:#555}.value{font-weight:700}</style>",
        f'<rect width="{width}" height="{height}" fill="white"/>',
        f'<text x="24" y="34" class="title">{html.escape(title)}</text>',
    ]
    for tick in [0, 0.25, 0.5, 0.75, 1.0]:
        x = left + tick * plot_w
        parts.append(f'<line x1="{x:.1f}" y1="{top - 16}" x2="{x:.1f}" y2="{height - bottom + 5}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{x:.1f}" y="{top - 22}" text-anchor="middle" class="axis">{tick:.0%}</text>')

    for i, row in enumerate(rows):
        y = top + i * row_h
        label = html.escape(str(row[label_key]))
        value = float(row[value_key])
        bar_w = 0 if max_value == 0 else min(value / max_value, 1.0) * plot_w
        value_text = f"{value:.1%}" if value_suffix == "%" else f"{value:.3f}{value_suffix}"
        parts.extend(
            [
                f'<text x="{left - 10}" y="{y + 18}" text-anchor="end">{label}</text>',
                f'<rect x="{left}" y="{y + 5}" width="{bar_w:.1f}" height="18" rx="2" fill="{palette}"/>',
                f'<text x="{left + bar_w + 7:.1f}" y="{y + 18}" class="value">{html.escape(value_text)}</text>',
            ]
        )
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--inputs",
        nargs="+",
        type=Path,
        default=[ROOT / "results"],
        help="Result directories, JSON files, or ZIP archives.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "analysis_outputs" / "latest",
        help="Directory for consolidated CSV and SVG outputs.",
    )
    parser.add_argument(
        "--include-tasks",
        nargs="*",
        help="Optional task-id allowlist, e.g. mg_parse_006 mg_parse_007.",
    )
    parser.add_argument(
        "--exclude-models",
        nargs="*",
        default=["example_bad", "example_reference"],
        help="Model names to exclude from summaries.",
    )
    parser.add_argument(
        "--include-models",
        nargs="*",
        help="Optional model-name allowlist. Useful for fixed-model paper plots.",
    )
    parser.add_argument(
        "--dedupe-by-source",
        action="store_true",
        help="Preserve duplicate model/task rows when they come from different sources.",
    )
    args = parser.parse_args()

    raw_rows = []
    for source, json_path in discover_json_files(args.inputs):
        row = parse_result_json(source, json_path)
        if row is not None:
            raw_rows.append(row)

    rows = dedupe_rows(raw_rows, include_source_in_key=args.dedupe_by_source)
    if args.include_tasks:
        allowed = set(args.include_tasks)
        rows = [row for row in rows if row.task_id in allowed]
    if args.exclude_models:
        excluded = set(args.exclude_models)
        rows = [row for row in rows if row.model not in excluded]
    if args.include_models:
        included = set(args.include_models)
        rows = [row for row in rows if row.model in included]

    if not rows:
        raise SystemExit("No result JSON rows found. Check --inputs.")

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    master_rows = [
        {
            "source": row.source,
            "model": row.model,
            "task_id": row.task_id,
            "task_label": TASK_LABELS.get(row.task_id, row.task_id),
            "task_family": task_family(row.task_id),
            "score": row.score,
            "passed": row.passed,
            "timeout": row.timeout,
            "failure_modes": ";".join(row.failure_modes),
            "repeat": row.repeat,
        }
        for row in sorted(rows, key=lambda row: (task_number(row.task_id), row.task_id, row.model, row.repeat))
    ]
    write_csv(
        output_dir / "master_results.csv",
        [
            "source",
            "model",
            "task_id",
            "task_label",
            "task_family",
            "score",
            "passed",
            "timeout",
            "failure_modes",
            "repeat",
        ],
        master_rows,
    )

    task_summary = summarize_by_task(rows)
    model_summary = summarize_by_model(rows)
    family_summary = summarize_by_family(rows)
    failure_summary = summarize_failures(rows)

    write_csv(output_dir / "summary_by_task.csv", list(task_summary[0]), task_summary)
    write_csv(output_dir / "summary_by_model.csv", list(model_summary[0]), model_summary)
    write_csv(output_dir / "summary_by_family.csv", list(family_summary[0]), family_summary)
    if failure_summary:
        write_csv(output_dir / "failure_modes_by_task.csv", list(failure_summary[0]), failure_summary)
    write_score_matrix(output_dir / "score_matrix.csv", rows)

    svg_bar_chart(
        output_dir / "task_pass_rate.svg",
        task_summary,
        "task_label",
        "pass_rate",
        "Pass Rate by Task",
        value_suffix="%",
        max_value=1.0,
    )
    svg_bar_chart(
        output_dir / "task_mean_score.svg",
        task_summary,
        "task_label",
        "mean_score",
        "Mean Score by Task",
        max_value=1.0,
    )
    svg_bar_chart(
        output_dir / "model_pass_rate.svg",
        model_summary,
        "model",
        "pass_rate",
        "Pass Rate by Model",
        value_suffix="%",
        max_value=1.0,
    )
    svg_bar_chart(
        output_dir / "family_pass_rate.svg",
        family_summary,
        "task_family",
        "pass_rate",
        "Pass Rate by Task Family",
        value_suffix="%",
        max_value=1.0,
    )

    print(f"[done] rows: {len(rows)}")
    print(f"[done] tasks: {len({row.task_id for row in rows})}")
    print(f"[done] models: {len({row.model for row in rows})}")
    print(f"[done] output: {output_dir}")
    print("[files]")
    for path in sorted(output_dir.iterdir()):
        print(f"  {path}")


if __name__ == "__main__":
    main()
