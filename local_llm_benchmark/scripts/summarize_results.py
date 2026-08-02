#!/usr/bin/env python3
"""
Summarize HEPToolBench result JSON files.

Example:
    python scripts/summarize_results.py --results results --out paper_results/generated
"""

import argparse
import csv
import json
from pathlib import Path

TASKS = [
    "mg_basic_001", "mg_debug_001", "mg_debug_structured_001", "mg_structured_001",
    "mg_basic_002", "mg_debug_002", "mg_debug_structured_002", "mg_structured_002",
    "mg_basic_003", "mg_debug_003", "mg_debug_structured_003", "mg_structured_003",
    "mg_runcard_004", "mg_runcard_structured_004",
    "mg_workflow_005", "mg_workflow_structured_005",
    "mg_parse_006", "mg_parse_007", "mg_parse_008", "mg_parse_009",
    "pythia_config_010", "delphes_objects_011", "lhe_sanity_012",
    "cutflow_diagnosis_013", "scan_plan_014", "param_card_patch_015",
    "scan_results_016", "scan_recovery_017", "benchmark_recommendation_018",
    "plot_data_019", "repro_audit_020",
]

INFRA_ERROR_WORDS = [
    "api error", "api_error", "sarvam_api_error", "github_api_error", "gemini_api_error",
    "mistral_api_error", "runner_error", "missing_runner", "traceback", "exception",
    "none object has no attribute", "nonetype", "content=null", "empty/null",
    "429", "rate limit", "quota", "too many requests", "not enough quota",
    "free-models-per-day", "bad gateway", "gateway timeout", "upstream connection closed",
    "service is unavailable", "502", "503", "504", "ollama_timeout", "ollama_nonzero_exit",
    "timeout_expired", "nonzero_exit",
]


def parse_model_task(path: Path):
    stem = path.stem
    for task in TASKS:
        suffix = "_" + task
        if stem.endswith(suffix):
            return stem[:-len(suffix)], task
    return None, None


def read_result(path: Path):
    text = path.read_text(errors="ignore")
    low = text.lower()
    try:
        data = json.loads(text)
        parsed = True
    except Exception:
        data = {}
        parsed = False

    failure_modes = data.get("failure_modes", "")
    if isinstance(failure_modes, list):
        failure_modes_text = ";".join(str(x) for x in failure_modes)
    else:
        failure_modes_text = str(failure_modes)

    error_text = str(data.get("error", ""))
    combined = "\n".join([low, failure_modes_text.lower(), error_text.lower()])

    score = data.get("score", "")
    passed = data.get("passed", "")
    try:
        score_float = float(score)
    except Exception:
        score_float = 0.0

    # Infrastructure/API failures are not valid model scores. Wrong model answers,
    # malformed JSON submissions, and failed semantic checks remain valid scored failures.
    infra_error_like = any(word in combined for word in INFRA_ERROR_WORDS)
    valid_scored = parsed and ("score" in data) and ("passed" in data) and not infra_error_like

    return {
        "score": score,
        "passed": passed,
        "valid_scored": valid_scored,
        "api_error_like": infra_error_like,
        "failure_modes": failure_modes_text,
        "error": error_text,
        "score_float": score_float,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default="results", help="Folder containing result JSON files")
    parser.add_argument("--out", default="paper_results", help="Output folder for CSV summaries")
    args = parser.parse_args()

    results_dir = Path(args.results)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for path in sorted(results_dir.glob("*.json")):
        model, task = parse_model_task(path)
        if model is None or task is None:
            continue
        info = read_result(path)
        rows.append({
            "model": model,
            "task_id": task,
            "score": info["score"],
            "passed": info["passed"],
            "valid_scored": info["valid_scored"],
            "api_error_like": info["api_error_like"],
            "result_file": str(path),
            "failure_modes": info["failure_modes"],
            "error": info["error"],
        })

    all_path = out_dir / "all_model_task_results.csv"
    with all_path.open("w", newline="") as f:
        fieldnames = [
            "model", "task_id", "score", "passed", "valid_scored",
            "api_error_like", "result_file", "failure_modes", "error",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    models = sorted(set(row["model"] for row in rows))
    summary_rows = []
    for model in models:
        model_rows = [row for row in rows if row["model"] == model]
        valid_rows = [row for row in model_rows if str(row["valid_scored"]).lower() == "true"]
        api_rows = [row for row in model_rows if str(row["api_error_like"]).lower() == "true"]
        present_tasks = set(row["task_id"] for row in model_rows)
        missing_tasks = [task for task in TASKS if task not in present_tasks]

        scores = []
        passed_count = 0
        for row in valid_rows:
            try:
                scores.append(float(row["score"]))
            except Exception:
                scores.append(0.0)
            if str(row["passed"]).lower() == "true":
                passed_count += 1
        mean_score = sum(scores) / len(scores) if scores else 0.0
        clean = len(valid_rows) == len(TASKS) and len(api_rows) == 0 and len(missing_tasks) == 0

        summary_rows.append({
            "model": model,
            "files_present": len(model_rows),
            "valid_scored": len(valid_rows),
            "api_error_like": len(api_rows),
            "missing": len(missing_tasks),
            "passed": passed_count,
            "mean_score_valid_only": round(mean_score, 6),
            "complete_clean_31": clean,
            "missing_tasks": ";".join(missing_tasks),
        })

    summary_path = out_dir / "model_summary.csv"
    with summary_path.open("w", newline="") as f:
        fieldnames = [
            "model", "files_present", "valid_scored", "api_error_like", "missing",
            "passed", "mean_score_valid_only", "complete_clean_31", "missing_tasks",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    by_model_task = {(row["model"], row["task_id"]): row for row in rows}

    score_matrix_path = out_dir / "score_matrix.csv"
    with score_matrix_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["model"] + TASKS)
        for model in models:
            line = [model]
            for task in TASKS:
                row = by_model_task.get((model, task))
                line.append(row["score"] if row and str(row["valid_scored"]).lower() == "true" else "")
            writer.writerow(line)

    pass_matrix_path = out_dir / "pass_matrix.csv"
    with pass_matrix_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["model"] + TASKS)
        for model in models:
            line = [model]
            for task in TASKS:
                row = by_model_task.get((model, task))
                line.append(row["passed"] if row and str(row["valid_scored"]).lower() == "true" else "")
            writer.writerow(line)

    print("Saved:")
    print(" ", all_path)
    print(" ", summary_path)
    print(" ", score_matrix_path)
    print(" ", pass_matrix_path)
    print()
    print("Model summary:")
    for row in summary_rows:
        print(
            f"{row['model']:40s} "
            f"valid={row['valid_scored']:2d}/{len(TASKS)} "
            f"passed={row['passed']:2d}/{row['valid_scored']:2d} "
            f"mean={row['mean_score_valid_only']:.4f} "
            f"clean={row['complete_clean_31']}"
        )


if __name__ == "__main__":
    main()
