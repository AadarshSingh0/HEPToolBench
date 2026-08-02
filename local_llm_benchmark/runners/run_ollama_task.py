#!/usr/bin/env python3
"""Run one HEPToolBench task against multiple Ollama models.

Edit MODELS_TO_TEST below, then run:
    python runners/run_ollama_task.py --task mg_basic_001

For stability testing:
    python runners/run_ollama_task.py --task mg_basic_001 --repeats 3

You can still override the list from the command line:
    python runners/run_ollama_task.py \
      --task mg_basic_001 \
      --models deepseek-r1:8b llama3:8b qwen2.5:7b
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
try:
    from runners.io_utils import ensure_output_dirs
    from runners.ollama_http_transport import (
        DEFAULT_NUM_CTX,
        TRANSPORT_NAME,
        OllamaTimeoutError,
        OllamaTransportError,
        generate,
    )
except ModuleNotFoundError:
    from io_utils import ensure_output_dirs
    from ollama_http_transport import (
        DEFAULT_NUM_CTX,
        TRANSPORT_NAME,
        OllamaTimeoutError,
        OllamaTransportError,
        generate,
    )


ROOT = Path(__file__).resolve().parents[1]

# Edit this list to control which local Ollama models are tested.
# Use the exact names shown by: ollama list
MODELS_TO_TEST = [
    "qwen2.5-coder:14b",
    "llama3:8b",
    "llama3.2-vision:11b",
    "gemma4:latest",
    "llama4:scout",
]

TASKS = {
    "mg_basic_001": {
        "prompt": ROOT / "tasks/mg_basic/task_001_drell_yan_template/prompt.md",
        "inputs": [
            ROOT / "tasks/mg_basic/task_001_drell_yan_template/input/proc_card_template.dat",
        ],
        "artifact": "proc_card.dat",
    },
    "mg_basic_002": {
        "prompt": ROOT / "tasks/mg_basic/task_002_top_pair_freeform/prompt.md",
        "inputs": [],
        "artifact": "proc_card.dat",
    },
    "mg_basic_003": {
        "prompt": ROOT / "tasks/mg_basic/task_003_higgs_jet_freeform/prompt.md",
        "inputs": [],
        "artifact": "proc_card.dat",
    },
    "mg_debug_001": {
        "prompt": ROOT / "tasks/mg_debug/task_001_drell_yan_repair/prompt.md",
        "inputs": [
            ROOT / "tasks/mg_debug/task_001_drell_yan_repair/input/broken_proc_card.dat",
        ],
        "artifact": "proc_card.dat",
    },
    "mg_debug_002": {
        "prompt": ROOT / "tasks/mg_debug/task_002_top_pair_repair/prompt.md",
        "inputs": [
            ROOT / "tasks/mg_debug/task_002_top_pair_repair/input/broken_proc_card.dat",
        ],
        "artifact": "proc_card.dat",
    },
    "mg_debug_003": {
        "prompt": ROOT / "tasks/mg_debug/task_003_higgs_jet_repair/prompt.md",
        "inputs": [
            ROOT / "tasks/mg_debug/task_003_higgs_jet_repair/input/broken_proc_card.dat",
        ],
        "artifact": "proc_card.dat",
    },
    "mg_debug_structured_001": {
        "prompt": ROOT / "tasks/mg_debug_structured/task_001_drell_yan_repair_json/prompt.md",
        "inputs": [
            ROOT / "tasks/mg_debug_structured/task_001_drell_yan_repair_json/input/broken_proc_card.dat",
        ],
        "artifact": "repair.json",
    },
    "mg_debug_structured_002": {
        "prompt": ROOT / "tasks/mg_debug_structured/task_002_top_pair_repair_json/prompt.md",
        "inputs": [
            ROOT / "tasks/mg_debug_structured/task_002_top_pair_repair_json/input/broken_proc_card.dat",
        ],
        "artifact": "repair.json",
    },
    "mg_debug_structured_003": {
        "prompt": ROOT / "tasks/mg_debug_structured/task_003_higgs_jet_repair_json/prompt.md",
        "inputs": [
            ROOT / "tasks/mg_debug_structured/task_003_higgs_jet_repair_json/input/broken_proc_card.dat",
        ],
        "artifact": "repair.json",
    },
    "mg_structured_001": {
        "prompt": ROOT / "tasks/mg_structured/task_001_drell_yan_json/prompt.md",
        "inputs": [],
        "artifact": "params.json",
    },
    "mg_structured_002": {
        "prompt": ROOT / "tasks/mg_structured/task_002_top_pair_json/prompt.md",
        "inputs": [],
        "artifact": "params.json",
    },
    "mg_structured_003": {
        "prompt": ROOT / "tasks/mg_structured/task_003_higgs_jet_json/prompt.md",
        "inputs": [],
        "artifact": "params.json",
    },
    "mg_runcard_004": {
        "prompt": ROOT / "tasks/mg_runcard/task_004_drell_yan_cuts_direct/prompt.md",
        "inputs": [],
        "artifact": "run_card.dat",
    },
    "mg_runcard_structured_004": {
        "prompt": ROOT / "tasks/mg_runcard_structured/task_004_drell_yan_cuts_json/prompt.md",
        "inputs": [],
        "artifact": "params.json",
    },
    "mg_workflow_005": {
        "prompt": ROOT / "tasks/mg_workflow/task_005_ttbar_pythia_delphes_direct/prompt.md",
        "inputs": [],
        "artifact": "mg5_script.txt",
    },
    "mg_workflow_structured_005": {
        "prompt": ROOT / "tasks/mg_workflow_structured/task_005_ttbar_pythia_delphes_json/prompt.md",
        "inputs": [],
        "artifact": "params.json",
    },
    "mg_parse_006": {
        "prompt": ROOT / "tasks/mg_parse/task_006_mg_log_summary_json/prompt.md",
        "inputs": [
            ROOT / "tasks/mg_parse/task_006_mg_log_summary_json/input/mg_run_summary.log",
        ],
        "artifact": "summary.json",
    },
    "mg_parse_007": {
        "prompt": ROOT / "tasks/mg_parse/task_007_mg_failure_diagnosis_json/prompt.md",
        "inputs": [
            ROOT / "tasks/mg_parse/task_007_mg_failure_diagnosis_json/input/mg_failed_run.log",
        ],
        "artifact": "diagnosis.json",
    },
    "mg_parse_008": {
        "prompt": ROOT / "tasks/mg_parse/task_008_mg_unit_conversion_json/prompt.md",
        "inputs": [
            ROOT / "tasks/mg_parse/task_008_mg_unit_conversion_json/input/mg_run_summary_fb.log",
        ],
        "artifact": "summary.json",
    },
    "mg_parse_009": {
        "prompt": ROOT / "tasks/mg_parse/task_009_mg_output_validation_json/prompt.md",
        "inputs": [
            ROOT / "tasks/mg_parse/task_009_mg_output_validation_json/input/mg_output_manifest.txt",
        ],
        "artifact": "validation.json",
    },
    "pythia_config_010": {
        "prompt": ROOT / "tasks/pythia/task_010_pythia_config_validation_json/prompt.md",
        "inputs": [
            ROOT / "tasks/pythia/task_010_pythia_config_validation_json/input/pythia8_ttbar.cmnd",
        ],
        "artifact": "validation.json",
    },
    "delphes_objects_011": {
        "prompt": ROOT / "tasks/delphes/task_011_delphes_object_validation_json/prompt.md",
        "inputs": [
            ROOT / "tasks/delphes/task_011_delphes_object_validation_json/input/delphes_object_summary.txt",
        ],
        "artifact": "validation.json",
    },
    "lhe_sanity_012": {
        "prompt": ROOT / "tasks/lhe/task_012_lhe_sanity_json/prompt.md",
        "inputs": [
            ROOT / "tasks/lhe/task_012_lhe_sanity_json/input/lhe_sanity_report.txt",
        ],
        "artifact": "sanity.json",
    },
    "cutflow_diagnosis_013": {
        "prompt": ROOT / "tasks/analysis/task_013_cutflow_diagnosis_json/prompt.md",
        "inputs": [
            ROOT / "tasks/analysis/task_013_cutflow_diagnosis_json/input/cutflow_table.txt",
        ],
        "artifact": "cutflow_diagnosis.json",
    },
    "scan_plan_014": {
        "prompt": ROOT / "tasks/scan/task_014_parameter_scan_plan_json/prompt.md",
        "inputs": [
            ROOT / "tasks/scan/task_014_parameter_scan_plan_json/input/scan_request.txt",
        ],
        "artifact": "scan_plan.json",
    },
    "param_card_patch_015": {
        "prompt": ROOT / "tasks/scan/task_015_param_card_patch_json/prompt.md",
        "inputs": [
            ROOT / "tasks/scan/task_015_param_card_patch_json/input/scan_point_request.txt",
            ROOT / "tasks/scan/task_015_param_card_patch_json/input/param_card_excerpt.dat",
        ],
        "artifact": "param_patch.json",
    },
    "scan_results_016": {
        "prompt": ROOT / "tasks/scan/task_016_scan_results_summary_json/prompt.md",
        "inputs": [
            ROOT / "tasks/scan/task_016_scan_results_summary_json/input/scan_results_table.txt",
        ],
        "artifact": "scan_summary.json",
    },
    "scan_recovery_017": {
        "prompt": ROOT / "tasks/scan/task_017_scan_recovery_plan_json/prompt.md",
        "inputs": [
            ROOT / "tasks/scan/task_017_scan_recovery_plan_json/input/intended_scan_grid.txt",
            ROOT / "tasks/scan/task_017_scan_recovery_plan_json/input/scan_job_manifest.txt",
        ],
        "artifact": "recovery_plan.json",
    },
    "benchmark_recommendation_018": {
        "prompt": ROOT / "tasks/scan/task_018_benchmark_recommendation_json/prompt.md",
        "inputs": [
            ROOT / "tasks/scan/task_018_benchmark_recommendation_json/input/final_scan_table.txt",
        ],
        "artifact": "recommendation.json",
    },
    "plot_data_019": {
        "prompt": ROOT / "tasks/scan/task_019_plot_data_json/prompt.md",
        "inputs": [
            ROOT / "tasks/scan/task_019_plot_data_json/input/completed_scan_with_benchmark.txt",
        ],
        "artifact": "plot_data.json",
    },
    "repro_audit_020": {
        "prompt": ROOT / "tasks/repro/task_020_reproducibility_audit_json/prompt.md",
        "inputs": [
            ROOT / "tasks/repro/task_020_reproducibility_audit_json/input/analysis_package_manifest.txt",
        ],
        "artifact": "repro_audit.json",
    },
}


def safe_model_name(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", model.replace(":", "_"))


def build_prompt(task_id: str) -> str:
    task = TASKS[task_id]
    parts = [
        "You are being tested on a particle-physics software benchmark.",
        "Return only the requested output file content. Do not include explanations.",
        "",
        "TASK INSTRUCTION:",
        task["prompt"].read_text().strip(),
    ]

    for input_path in task["inputs"]:
        parts.extend(
            [
                "",
                f"INPUT FILE: {input_path.name}",
                "```text",
                input_path.read_text().rstrip(),
                "```",
            ]
        )

    return "\n".join(parts).strip() + "\n"


def run_ollama(
    model: str,
    prompt: str,
    timeout: int,
    num_ctx: int = DEFAULT_NUM_CTX,
) -> tuple[str, dict]:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    return generate(
        host=host,
        model=model,
        prompt=prompt,
        timeout=timeout,
        num_ctx=num_ctx,
    )


def evaluate(task_id: str, submission: Path, result_path: Path) -> dict:
    cmd = [
        sys.executable,
        str(ROOT / "runners/evaluate_submission.py"),
        "--task",
        task_id,
        "--submission",
        str(submission),
        "--output",
        str(result_path),
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=True)
    return json.loads(proc.stdout)


def run_single_attempt(
    *,
    model: str,
    task_id: str,
    prompt: str,
    timeout: int,
    submission_dir: Path,
    result_path: Path,
    num_ctx: int = DEFAULT_NUM_CTX,
) -> dict:
    submission_path = submission_dir / TASKS[task_id]["artifact"]
    metadata_path = submission_dir / "ollama_http_metadata.json"

    submission_dir.mkdir(parents=True, exist_ok=True)
    result_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        stdout, transport_metadata = run_ollama(
            model,
            prompt,
            timeout,
            num_ctx,
        )
    except OllamaTransportError as exc:
        error_metadata = dict(exc.metadata)
        error_metadata["error"] = {
            "failure_mode": exc.failure_mode,
            "message": str(exc),
        }
        metadata_path.write_text(
            json.dumps(error_metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        result = {
            "task_id": task_id,
            "model": model,
            "score": 0.0 if isinstance(exc, OllamaTimeoutError) else None,
            "passed": False if isinstance(exc, OllamaTimeoutError) else None,
            "failure_modes": [exc.failure_mode],
            "valid_for_scoring": isinstance(exc, OllamaTimeoutError),
            "runner_error": not isinstance(exc, OllamaTimeoutError),
            "ollama_transport": TRANSPORT_NAME,
            "ollama_num_ctx": num_ctx,
            "ollama_http_metadata_file": str(metadata_path),
        }
        result_path.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if isinstance(exc, OllamaTimeoutError):
            return result
        raise

    metadata_path.write_text(
        json.dumps(transport_metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    saved_text = stdout.strip() + "\n"
    submission_path.write_text(saved_text, encoding="utf-8")

    result = evaluate(task_id, submission_path, result_path)
    response_metadata = transport_metadata.get("response", {})
    identity = transport_metadata.get("model_identity", {})
    result.update(
        {
            "model": model,
            "valid_for_scoring": True,
            "runner_error": False,
            "ollama_transport": TRANSPORT_NAME,
            "ollama_num_ctx": num_ctx,
            "ollama_model_digest": identity.get("digest"),
            "ollama_done_reason": response_metadata.get("done_reason"),
            "ollama_prompt_eval_count": response_metadata.get("prompt_eval_count"),
            "ollama_eval_count": response_metadata.get("eval_count"),
            "ollama_output_truncated": response_metadata.get("done_reason") == "length",
            "ollama_output_sha256": transport_metadata.get("output", {}).get("sha256"),
            "artifact_sha256": hashlib.sha256(
                saved_text.encode("utf-8")
            ).hexdigest(),
            "ollama_http_metadata_file": str(metadata_path),
        }
    )
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def write_leaderboard(
    task_id: str,
    rows: list[dict],
    output_root: Path = ROOT,
) -> Path:
    leaderboard_path = output_root / "results" / f"leaderboard_{task_id}.csv"
    with leaderboard_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["model", "task_id", "score", "passed", "failure_modes"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "model": row.get("model"),
                    "task_id": row.get("task_id", task_id),
                    "score": row.get("score"),
                    "passed": row.get("passed"),
                    "failure_modes": ";".join(row.get("failure_modes", [])),
                }
            )
    return leaderboard_path


def write_stability_report(
    task_id: str,
    models: list[str],
    rows: list[dict],
    output_root: Path = ROOT,
) -> Path:
    report_path = output_root / "results" / f"stability_{task_id}.csv"
    by_model: dict[str, list[dict]] = {model: [] for model in models}
    for row in rows:
        by_model.setdefault(row.get("model", ""), []).append(row)

    with report_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "model",
                "task_id",
                "runs",
                "passes",
                "pass_rate",
                "mean_score",
                "common_failure_modes",
            ],
        )
        writer.writeheader()
        for model in models:
            model_rows = by_model.get(model, [])
            runs = len(model_rows)
            passes = sum(1 for row in model_rows if row.get("passed") is True)
            scores = [float(row.get("score") or 0.0) for row in model_rows]
            mean_score = sum(scores) / runs if runs else 0.0
            failure_counts: dict[str, int] = {}
            for row in model_rows:
                for failure in row.get("failure_modes", []):
                    failure_counts[failure] = failure_counts.get(failure, 0) + 1
            common_failures = sorted(
                failure_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
            common_failure_modes = ";".join(f"{name}:{count}" for name, count in common_failures)
            writer.writerow(
                {
                    "model": model,
                    "task_id": task_id,
                    "runs": runs,
                    "passes": passes,
                    "pass_rate": round(passes / runs, 3) if runs else 0.0,
                    "mean_score": round(mean_score, 3),
                    "common_failure_modes": common_failure_modes,
                }
            )
    return report_path


def main() -> None:
    ensure_output_dirs()
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", default="mg_basic_001", choices=sorted(TASKS))
    parser.add_argument(
        "--models",
        nargs="+",
        help="One or more Ollama model names.",
    )
    parser.add_argument(
        "--model",
        action="append",
        help="Single-model alias; may be repeated.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT,
        help="Root directory for results and submissions.",
    )
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--num-ctx",
        type=int,
        default=DEFAULT_NUM_CTX,
        help=f"Explicit Ollama context window (default: {DEFAULT_NUM_CTX}).",
    )
    parser.add_argument("--repeats", type=int, default=1, help="Number of repeated attempts per model.")
    parser.add_argument("--dry-run", action="store_true", help="Print the prompt and exit without calling Ollama.")
    args = parser.parse_args()

    if args.models and args.model:
        parser.error("Use either --model or --models, not both.")

    models = args.models or args.model or MODELS_TO_TEST
    if not models:
        raise SystemExit("No models selected. Pass --model or --models.")

    output_root = args.output_root.expanduser().resolve()
    (output_root / "results").mkdir(parents=True, exist_ok=True)
    (output_root / "submissions").mkdir(parents=True, exist_ok=True)

    prompt = build_prompt(args.task)
    if args.dry_run:
        print(prompt)
        return

    rows = []
    print(f"[task] {args.task}")
    print(f"[models] {', '.join(models)}")
    print(f"[repeats] {args.repeats}")
    print(f"[transport] {TRANSPORT_NAME}")
    print(f"[num_ctx] {args.num_ctx}")

    for model in models:
        model_id = safe_model_name(model)
        for repeat_index in range(1, args.repeats + 1):
            if args.repeats == 1:
                submission_dir = output_root / "submissions" / model_id / args.task
                result_path = output_root / "results" / f"{model_id}_{args.task}.json"
            else:
                submission_dir = output_root / "submissions" / model_id / args.task / f"run_{repeat_index}"
                result_path = output_root / "results" / f"{model_id}_{args.task}_run_{repeat_index}.json"

            print(f"[run] {model} repeat={repeat_index}/{args.repeats} -> {submission_dir}")
            result = run_single_attempt(
                model=model,
                task_id=args.task,
                prompt=prompt,
                timeout=args.timeout,
                submission_dir=submission_dir,
                result_path=result_path,
                num_ctx=args.num_ctx,
            )
            result["repeat"] = repeat_index
            rows.append(result)
            print(
                f"[score] {model} repeat={repeat_index}: "
                f"score={result.get('score')} passed={result.get('passed')}"
            )

    leaderboard_path = write_leaderboard(args.task, rows, output_root)
    print(f"[done] leaderboard: {leaderboard_path}")
    if args.repeats > 1:
        stability_path = write_stability_report(
            args.task, models, rows, output_root
        )
        print(f"[done] stability: {stability_path}")


if __name__ == "__main__":
    main()
