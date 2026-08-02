#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import traceback
from pathlib import Path
try:
    from runners.io_utils import ensure_output_dirs
except ModuleNotFoundError:
    from io_utils import ensure_output_dirs

from google import genai

# Reuse the exact same task registry, prompt builder, scorer, and naming style
# from the Ollama runner.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runners"))
import run_ollama_task as base  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]

TASK_ORDER = [
    "mg_basic_001",
    "mg_debug_001",
    "mg_debug_structured_001",
    "mg_debug_structured_002",
    "mg_debug_structured_003",
    "mg_structured_001",
    "mg_basic_002",
    "mg_debug_002",
    "mg_structured_002",
    "mg_basic_003",
    "mg_debug_003",
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

# For the final paper, we can later select exactly the canonical 20-task set.
# For now, --task all runs every task known in TASK_ORDER that exists in TASKS.


def safe_model_name(model: str) -> str:
    return (
        model.replace("/", "_")
        .replace(":", "_")
        .replace(".", "_")
        .replace("-", "-")
    )


def call_gemini(client, model: str, prompt: str, timeout: int) -> str:
    # Google SDK call is blocking; timeout is not directly enforced by SDK here.
    # We keep timeout in the metadata/logging for consistency.

    generation_config = {
        "temperature": 0.0,
    }

    # gemini-2.5-flash-lite rejects the SDK's "low" thinking level because
    # it maps to thinking_budget=256, while this model requires >=512.
    # For flash-lite, let the API choose its valid default.
    if "flash-lite" not in model:
        generation_config["thinking_level"] = "low"

    interaction = client.interactions.create(
        model=model,
        system_instruction=(
            "You are being evaluated in a particle-physics software benchmark. "
            "Return only the requested output file content. Do not include explanations."
        ),
        input=prompt,
        generation_config=generation_config,
    )
    return interaction.output_text or ""


def run_one_task(model: str, task_id: str, timeout: int, sleep_s: float = 1.0) -> dict:
    prompt = base.build_prompt(task_id)

    model_id = safe_model_name(model)
    submission_dir = ROOT / "submissions" / model_id / task_id
    submission_dir.mkdir(parents=True, exist_ok=True)

    artifact = base.TASKS[task_id]["artifact"]
    submission_path = submission_dir / artifact
    stderr_path = submission_dir / "gemini_stderr.txt"
    result_path = ROOT / "results" / f"{model_id}_{task_id}.json"

    client = genai.Client()

    print(f"[run] {model} -> {task_id}")
    try:
        output = call_gemini(client, model, prompt, timeout)
        submission_path.write_text(output.strip() + "\n")
        stderr_path.write_text("")
    except Exception as exc:
        err = traceback.format_exc()
        stderr_path.write_text(err)
        result = {
            "task_id": task_id,
            "model": model,
            "score": 0.0,
            "passed": False,
            "failure_modes": ["gemini_api_error"],
            "error": str(exc),
        }
        result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(f"[error] {task_id}: {exc}")
        return result

    try:
        result = base.evaluate(task_id, submission_path, result_path)
    except Exception as exc:
        result = {
            "task_id": task_id,
            "model": model,
            "score": 0.0,
            "passed": False,
            "failure_modes": ["evaluation_error"],
            "error": str(exc),
        }
        result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

    result["model"] = model
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"[score] {task_id}: score={result.get('score')} passed={result.get('passed')}")

    if sleep_s:
        time.sleep(sleep_s)

    return result


def write_leaderboard(model: str, rows: list[dict]) -> Path:
    model_id = safe_model_name(model)
    out = ROOT / "results" / f"leaderboard_{model_id}_gemini.csv"
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["model", "task_id", "score", "passed", "failure_modes"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "model": model,
                    "task_id": row.get("task_id"),
                    "score": row.get("score"),
                    "passed": row.get("passed"),
                    "failure_modes": ";".join(row.get("failure_modes", [])),
                }
            )
    return out


def main() -> None:
    ensure_output_dirs()
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gemini-3.5-flash")
    parser.add_argument(
        "--task",
        default="mg_structured_001",
        help="Task ID or 'all'.",
    )
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--sleep", type=float, default=1.0)
    args = parser.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("GEMINI_API_KEY is not set. Run: export GEMINI_API_KEY='...'")

    if args.task == "all":
        tasks = [t for t in TASK_ORDER if t in base.TASKS]
    else:
        if args.task not in base.TASKS:
            raise SystemExit(f"Unknown task: {args.task}")
        tasks = [args.task]

    rows = []
    print(f"[model] {args.model}")
    print(f"[tasks] {len(tasks)}")

    for task_id in tasks:
        rows.append(run_one_task(args.model, task_id, args.timeout, args.sleep))

    leaderboard = write_leaderboard(args.model, rows)
    print(f"[done] leaderboard: {leaderboard}")


if __name__ == "__main__":
    main()
