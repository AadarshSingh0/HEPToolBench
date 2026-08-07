#!/usr/bin/env python3
"""Beginner-friendly local Ollama benchmark runner for HEPToolBench v1.2.

Every invocation creates an isolated run directory and updates both a per-run
long CSV and a cumulative long CSV. Existing runs are never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from runners.run_ollama_task import TASKS, build_prompt, run_single_attempt, safe_model_name  # noqa: E402
from runners.ollama_generation_settings import (  # noqa: E402
    ENV_NUM_PREDICT,
    ENV_SEED,
    ENV_TEMPERATURE,
    ENV_THINK,
    normalize_ollama_generation_settings,
    ollama_generation_setting_mismatches,
)
from runners.ollama_http_transport import (  # noqa: E402
    DEFAULT_NUM_CTX,
    TRANSPORT_NAME,
    OllamaTransportError,
    clear_model_caches,
    control_character_summary,
    get_model_identity,
    installed_model_names,
    sha256_text,
)
from scripts.build_universal_csv import rebuild_outputs  # noqa: E402

EXTENSION3 = [
    "mg_debug_structured_001",
    "mg_debug_structured_002",
    "mg_debug_structured_003",
]
FULL31 = list(TASKS)
MAIN28 = [task for task in FULL31 if task not in set(EXTENSION3)]


def cli_option_present(option: str) -> bool:
    return any(
        arg == option or arg.startswith(option + "=")
        for arg in sys.argv[1:]
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}_{uuid.uuid4().hex[:6]}"


def relative_to_root(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected_model_identities(
    host: str,
    models: list[str],
) -> dict[str, dict[str, Any]]:
    identities: dict[str, dict[str, Any]] = {}
    for model in models:
        identity = get_model_identity(host, model)
        digest = identity.get("digest")
        if not isinstance(digest, str) or not digest:
            raise RuntimeError(
                f"Ollama did not provide a digest for model {model!r}; "
                "the benchmark will not start without a pinned model identity."
            )
        identities[model] = identity
    return identities


def verify_model_identities(
    expected: dict[str, Any],
    current: dict[str, dict[str, Any]],
) -> None:
    for model, current_identity in current.items():
        expected_identity = expected.get(model)
        if not isinstance(expected_identity, dict):
            raise RuntimeError(
                f"Saved run manifest has no identity record for {model!r}."
            )
        expected_digest = expected_identity.get("digest")
        current_digest = current_identity.get("digest")
        if expected_digest != current_digest:
            raise RuntimeError(
                "Refusing to mix model revisions while resuming: "
                f"{model!r} changed from digest {expected_digest!r} "
                f"to {current_digest!r}."
            )


def ollama_command(
    arguments: list[str],
    *,
    host: str,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["ollama", *arguments],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=timeout,
        env={**os.environ, "OLLAMA_HOST": host},
    )


def installed_models(host: str) -> list[str]:
    try:
        return installed_model_names(host, timeout=60)
    except OllamaTransportError as exc:
        raise RuntimeError(
            "Ollama is not available. Install/start Ollama or set "
            f"OLLAMA_HOST to a reachable server. Details: {exc}"
        ) from exc


def choose_models(models: list[str]) -> list[str]:
    print("\nInstalled Ollama models\n=======================")
    for index, model in enumerate(models, start=1):
        print(f"  {index:2d}. {model}")
    print("\nEnter 'a' for all models or comma-separated numbers such as 1,3,4.")

    raw = input("Models [a]: ").strip().lower() or "a"
    if raw in {"a", "all"}:
        return models

    selected: list[str] = []
    for token in raw.replace(" ", "").split(","):
        try:
            number = int(token)
        except ValueError as exc:
            raise RuntimeError(f"Invalid model selection: {token!r}") from exc
        if number < 1 or number > len(models):
            raise RuntimeError(f"Model number is out of range: {number}")
        selected.append(models[number - 1])
    return list(dict.fromkeys(selected))


def choose_suite() -> tuple[str, list[str]]:
    print("\nBenchmark suite\n===============")
    print("  1. Full 31-task suite")
    print("  2. Main 28-task suite")
    print("  3. Three structured-debug extension tasks")
    print("  4. Custom task IDs")

    raw = input("Suite [1]: ").strip() or "1"
    if raw == "1":
        return "full31", FULL31
    if raw == "2":
        return "main28", MAIN28
    if raw == "3":
        return "extension3", EXTENSION3
    if raw == "4":
        print("\nAvailable task IDs:")
        for task_id in FULL31:
            print(f"  {task_id}")
        custom = input("Enter comma-separated task IDs: ").strip()
        tasks = [item.strip() for item in custom.split(",") if item.strip()]
        unknown = sorted(set(tasks) - set(FULL31))
        if unknown:
            raise RuntimeError("Unknown task IDs: " + ", ".join(unknown))
        if not tasks:
            raise RuntimeError("No tasks selected.")
        return "custom", list(dict.fromkeys(tasks))
    raise RuntimeError(f"Invalid suite selection: {raw!r}")


def choose_repeats() -> int:
    raw = input("Number of repeats [1]: ").strip() or "1"
    try:
        repeats = int(raw)
    except ValueError as exc:
        raise RuntimeError("Repeats must be an integer.") from exc
    if repeats < 1:
        raise RuntimeError("Repeats must be at least 1.")
    return repeats


def confirm_plan(models: list[str], tasks: list[str], repeats: int) -> bool:
    calls = len(models) * len(tasks) * repeats
    print("\nPlanned evaluation\n==================")
    print(f"Models:      {len(models)}")
    print(f"Tasks:       {len(tasks)}")
    print(f"Repeats:     {repeats}")
    print(f"Total calls: {calls}")
    response = input("\nStart benchmark? [Y/n]: ").strip().lower()
    return response in {"", "y", "yes"}


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def load_manifest(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "run_manifest.json"
    if not path.is_file():
        raise RuntimeError(f"Run manifest not found: {path}")
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid run manifest: {path}")
    return data


def resolve_run_dir(value: str) -> Path:
    candidate = Path(value).expanduser()
    if candidate.is_dir():
        return candidate.resolve()
    candidate = ROOT / "runs" / value
    if candidate.is_dir():
        return candidate.resolve()
    raise RuntimeError(f"Cannot find run to resume: {value}")


def result_path_for(run_dir: Path, model: str, task_id: str, repeat: int) -> Path:
    return (
        run_dir
        / "results"
        / safe_model_name(model)
        / task_id
        / f"repeat_{repeat:03d}.json"
    )


def submission_dir_for(run_dir: Path, model: str, task_id: str, repeat: int) -> Path:
    return (
        run_dir
        / "submissions"
        / safe_model_name(model)
        / task_id
        / f"repeat_{repeat:03d}"
    )


def raw_response_path_for(run_dir: Path, model: str, task_id: str, repeat: int) -> Path:
    return (
        run_dir
        / "raw_responses"
        / safe_model_name(model)
        / task_id
        / f"repeat_{repeat:03d}.txt"
    )


def valid_result(path: Path) -> bool:
    # Explicitly deferred infrastructure-invalid entries may be skipped.
    # They remain invalid for scoring and must be repaired later.
    try:
        deferred_data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        deferred_data = None
    if (
        isinstance(deferred_data, dict)
        and deferred_data.get("skip_on_resume") is True
    ):
        return True

    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    required = {"run_id", "model", "task_id", "repeat", "score", "passed"}
    return (
        required.issubset(data)
        and data.get("valid_for_scoring") is True
        and data.get("runner_error") is False
    )


def partition_for(task_id: str) -> str:
    return "structured_debug_extension" if task_id in EXTENSION3 else "main28"


def pull_missing_models(selected: list[str], installed: list[str], *, host: str) -> None:
    missing = [model for model in selected if model not in set(installed)]
    for model in missing:
        print(f"[pull] {model}")
        result = ollama_command(["pull", model], host=host, timeout=10800)
        if result.returncode != 0:
            raise RuntimeError(f"Could not pull {model}:\n{result.stdout.strip()}")
    if missing:
        clear_model_caches()


def run_attempt(
    *,
    run_dir: Path,
    run_id: str,
    model: str,
    task_id: str,
    repeat: int,
    timeout: int,
    host: str,
    num_ctx: int,
) -> dict[str, Any]:
    result_path = result_path_for(run_dir, model, task_id, repeat)
    submission_dir = submission_dir_for(run_dir, model, task_id, repeat)
    raw_path = raw_response_path_for(run_dir, model, task_id, repeat)

    result_path.parent.mkdir(parents=True, exist_ok=True)
    submission_dir.mkdir(parents=True, exist_ok=True)
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    started_at = utc_now()
    started = time.monotonic()
    runner_error = False

    try:
        result = run_single_attempt(
            model=model,
            task_id=task_id,
            prompt=build_prompt(task_id),
            timeout=timeout,
            submission_dir=submission_dir,
            result_path=result_path,
            num_ctx=num_ctx,
        )
    except OllamaTransportError as exc:
        runner_error = True
        result = {
            "task_id": task_id,
            "model": model,
            "score": None,
            "passed": None,
            "failure_modes": [exc.failure_mode],
            "runner_exception": str(exc),
            "valid_for_scoring": False,
            "runner_error": True,
            "ollama_transport": TRANSPORT_NAME,
            "ollama_num_ctx": num_ctx,
        }
    except Exception as exc:
        runner_error = True
        result = {
            "task_id": task_id,
            "model": model,
            "score": None,
            "passed": None,
            "failure_modes": [f"runner_exception:{type(exc).__name__}"],
            "runner_exception": str(exc),
            "valid_for_scoring": False,
            "runner_error": True,
            "ollama_transport": TRANSPORT_NAME,
            "ollama_num_ctx": num_ctx,
        }

    completed_at = utc_now()
    wall_time = time.monotonic() - started

    artifact_path = submission_dir / TASKS[task_id]["artifact"]
    if artifact_path.is_file():
        shutil.copy2(artifact_path, raw_path)
    else:
        raw_path.write_text("")

    failures = result.get("failure_modes") or []
    if isinstance(failures, str):
        failures = [failures]

    result.update(
        {
            "run_id": run_id,
            "repeat": repeat,
            "started_at": started_at,
            "completed_at": completed_at,
            "provider_or_runtime": "local_ollama",
            "ollama_host": host,
            "ollama_transport": TRANSPORT_NAME,
            "ollama_num_ctx": num_ctx,
            "task_partition": partition_for(task_id),
            "timeout": any("timeout" in str(item).lower() for item in failures),
            "runner_error": runner_error or bool(result.get("runner_error")),
            "wall_time_seconds": round(wall_time, 6),
            "submission_file": relative_to_root(artifact_path),
            "raw_response_file": relative_to_root(raw_path),
        }
    )
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def audit_run_integrity(
    *,
    run_dir: Path,
    models: list[str],
    tasks: list[str],
    repeats: int,
    model_identities: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    planned = len(models) * len(tasks) * repeats
    observed_keys: set[tuple[str, str, int]] = set()
    duplicate_keys: list[dict[str, Any]] = []
    missing_results: list[str] = []
    invalid_results: list[str] = []
    missing_artifacts: list[str] = []
    missing_metadata: list[str] = []
    contaminated_artifacts: list[dict[str, Any]] = []
    invalid_utf8_artifacts: list[str] = []
    runner_errors: list[str] = []
    timeouts: list[str] = []
    truncated_outputs: list[str] = []
    digest_mismatches: list[dict[str, Any]] = []

    for model in models:
        expected_digest = model_identities[model]["digest"]
        for repeat in range(1, repeats + 1):
            for task_id in tasks:
                result_path = result_path_for(
                    run_dir,
                    model,
                    task_id,
                    repeat,
                )
                submission_dir = submission_dir_for(
                    run_dir,
                    model,
                    task_id,
                    repeat,
                )
                artifact_path = submission_dir / TASKS[task_id]["artifact"]
                metadata_path = submission_dir / "ollama_http_metadata.json"

                if not result_path.is_file():
                    missing_results.append(relative_to_root(result_path))
                    continue
                try:
                    result = json.loads(result_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    invalid_results.append(relative_to_root(result_path))
                    continue
                if not isinstance(result, dict):
                    invalid_results.append(relative_to_root(result_path))
                    continue

                repeat_value = result.get("repeat")
                repeat_key = repeat_value if isinstance(repeat_value, int) else -1
                key = (
                    str(result.get("model")),
                    str(result.get("task_id")),
                    repeat_key,
                )
                if key in observed_keys:
                    duplicate_keys.append(
                        {
                            "model": key[0],
                            "task_id": key[1],
                            "repeat": key[2],
                        }
                    )
                observed_keys.add(key)

                if (
                    result.get("valid_for_scoring") is not True
                    or not isinstance(result.get("score"), (int, float))
                    or not isinstance(result.get("passed"), bool)
                ):
                    invalid_results.append(relative_to_root(result_path))
                if result.get("runner_error") is True:
                    runner_errors.append(relative_to_root(result_path))
                if result.get("timeout") is True:
                    timeouts.append(relative_to_root(result_path))
                if result.get("ollama_output_truncated") is True:
                    truncated_outputs.append(relative_to_root(result_path))
                if result.get("ollama_model_digest") != expected_digest:
                    digest_mismatches.append(
                        {
                            "result": relative_to_root(result_path),
                            "expected": expected_digest,
                            "observed": result.get("ollama_model_digest"),
                        }
                    )

                if not metadata_path.is_file():
                    missing_metadata.append(relative_to_root(metadata_path))
                if not artifact_path.is_file():
                    missing_artifacts.append(relative_to_root(artifact_path))
                    continue
                try:
                    artifact_text = artifact_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    invalid_utf8_artifacts.append(
                        relative_to_root(artifact_path)
                    )
                    continue
                controls = control_character_summary(artifact_text)
                if controls["forbidden_total"]:
                    contaminated_artifacts.append(
                        {
                            "artifact": relative_to_root(artifact_path),
                            "control_characters": controls,
                        }
                    )

    checks = {
        "planned_evaluations": planned,
        "observed_unique_evaluations": len(observed_keys),
        "missing_results": missing_results,
        "invalid_results": sorted(set(invalid_results)),
        "duplicate_model_task_repeat_keys": duplicate_keys,
        "missing_artifacts": missing_artifacts,
        "missing_http_metadata": missing_metadata,
        "invalid_utf8_artifacts": invalid_utf8_artifacts,
        "contaminated_artifacts": contaminated_artifacts,
        "runner_errors": runner_errors,
        "timeouts": timeouts,
        "truncated_outputs": truncated_outputs,
        "model_digest_mismatches": digest_mismatches,
    }
    audit_passed = (
        len(observed_keys) == planned
        and not any(
            checks[name]
            for name in (
                "missing_results",
                "invalid_results",
                "duplicate_model_task_repeat_keys",
                "missing_artifacts",
                "missing_http_metadata",
                "invalid_utf8_artifacts",
                "contaminated_artifacts",
                "runner_errors",
                "timeouts",
                "truncated_outputs",
                "model_digest_mismatches",
            )
        )
    )
    audit = {
        "schema_version": 1,
        "transport": TRANSPORT_NAME,
        "passed": audit_passed,
        "checks": checks,
    }
    audit_path = run_dir / "integrity_audit.json"
    audit_path.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run local Ollama models over HEPToolBench and build long-form CSV files."
    )
    parser.add_argument(
        "--models",
        nargs="+",
        help="Exact Ollama model names, or 'all-installed'. Omit for the guided menu.",
    )
    parser.add_argument("--suite", choices=["full31", "main28", "extension3"])
    parser.add_argument("--tasks", nargs="+", help="Explicit task IDs; overrides --suite.")
    parser.add_argument("--repeats", type=int)
    parser.add_argument(
        "--timeout",
        type=int,
        default=1800,
        help="Per-model-task timeout in seconds (default: 1800).",
    )
    parser.add_argument(
        "--num-ctx",
        type=int,
        default=DEFAULT_NUM_CTX,
        help=(
            "Explicit Ollama context window recorded for every request "
            f"(default: {DEFAULT_NUM_CTX})."
        ),
    )
    parser.add_argument(
        "--ollama-host",
        default=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
    )
    parser.add_argument("--run-id")
    parser.add_argument("--resume", help="Existing run directory or run ID.")
    parser.add_argument("--pull-missing", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list-models", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if len(FULL31) != 31:
        raise RuntimeError(f"Expected 31 registered tasks, found {len(FULL31)}.")
    if args.timeout < 1:
        raise RuntimeError("--timeout must be at least 1 second.")
    if args.num_ctx < 1:
        raise RuntimeError("--num-ctx must be at least 1.")

    host = args.ollama_host.rstrip("/")
    os.environ["OLLAMA_HOST"] = host

    if args.list_models:
        available = installed_models(host)
        for model in available:
            print(model)
        return

    if args.resume:
        run_dir = resolve_run_dir(args.resume)
        manifest = load_manifest(run_dir)
        if (
            manifest.get("schema_version") != 2
            or manifest.get("ollama_transport") != TRANSPORT_NAME
        ):
            raise RuntimeError(
                "This run predates the corrected HTTP transport and cannot be "
                "resumed safely. Start a new run ID; keep the legacy run quarantined."
            )
        run_id = str(manifest["run_id"])
        models = [str(item) for item in manifest["models"]]
        tasks = [str(item) for item in manifest["tasks"]]
        repeats = int(manifest["repeats"])
        timeout = int(manifest["timeout_seconds"])
        num_ctx = int(manifest["num_ctx"])

        saved_ollama_settings = manifest.get(
            "ollama_generation_settings", {}
        )
        if not isinstance(saved_ollama_settings, dict):
            raise RuntimeError(
                "Run manifest contains invalid ollama_generation_settings."
            )

        resume_environment = {
            "think": ENV_THINK,
            "temperature": ENV_TEMPERATURE,
            "seed": ENV_SEED,
            "num_predict": ENV_NUM_PREDICT,
        }

        saved_normalized = normalize_ollama_generation_settings(
            num_ctx=num_ctx,
            think=saved_ollama_settings.get("think", "auto"),
            temperature=saved_ollama_settings.get("temperature", "auto"),
            seed=saved_ollama_settings.get("seed", "auto"),
            num_predict=saved_ollama_settings.get("num_predict", "auto"),
        )

        requested_normalized = normalize_ollama_generation_settings(
            num_ctx=args.num_ctx,
            think=os.environ.get(ENV_THINK),
            temperature=os.environ.get(ENV_TEMPERATURE),
            seed=os.environ.get(ENV_SEED),
            num_predict=os.environ.get(ENV_NUM_PREDICT),
        )

        explicit_resume_settings = set()

        if cli_option_present("--num-ctx"):
            explicit_resume_settings.add("num_ctx")

        for key, env_name in resume_environment.items():
            if env_name in os.environ:
                explicit_resume_settings.add(key)

        mismatches = ollama_generation_setting_mismatches(
            saved_normalized,
            requested_normalized,
            explicit_resume_settings,
        )

        if mismatches:
            details = ", ".join(
                f"{key}: saved={saved_value!r}, requested={requested_value!r}"
                for key, saved_value, requested_value in mismatches
            )
            raise RuntimeError(
                "Cannot change Ollama serving settings while resuming "
                f"{run_id}: {details}. "
                "Start a new run ID to use different serving settings."
            )

        for key, env_name in resume_environment.items():
            value = saved_ollama_settings.get(key, "auto")

            if value is None:
                value = "auto"
            elif isinstance(value, bool):
                value = "true" if value else "false"

            os.environ[env_name] = str(value)

        host = str(manifest.get("ollama_host", host)).rstrip("/")
        os.environ["OLLAMA_HOST"] = host

        available = installed_models(host)
        missing = [model for model in models if model not in set(available)]

        if missing and args.pull_missing:
            pull_missing_models(models, available, host=host)
            available = installed_models(host)
            missing = [model for model in models if model not in set(available)]

        if missing:
            raise RuntimeError(
                "These models from the saved run are not installed on its "
                "Ollama server: "
                + ", ".join(missing)
                + ". Use --pull-missing or install them before resuming."
            )

        model_identities = selected_model_identities(host, models)
        verify_model_identities(
            manifest.get("model_identities", {}),
            model_identities,
        )
        manifest["status"] = "running"
        manifest["resumed_at"] = utc_now()
        write_manifest(run_dir / "run_manifest.json", manifest)
    else:
        available = installed_models(host)
        if args.models:
            models = available if args.models == ["all-installed"] else list(dict.fromkeys(args.models))
        elif args.yes:
            models = available
        else:
            models = choose_models(available)

        if args.tasks:
            unknown = sorted(set(args.tasks) - set(FULL31))
            if unknown:
                raise RuntimeError("Unknown task IDs: " + ", ".join(unknown))
            tasks = list(dict.fromkeys(args.tasks))
            suite_name = "custom"
        elif args.suite:
            suite_name = args.suite
            tasks = {
                "full31": FULL31,
                "main28": MAIN28,
                "extension3": EXTENSION3,
            }[args.suite]
        elif args.yes:
            suite_name = "full31"
            tasks = FULL31
        else:
            suite_name, tasks = choose_suite()

        repeats = args.repeats if args.repeats is not None else (1 if args.yes else choose_repeats())
        timeout = args.timeout
        num_ctx = args.num_ctx
        if repeats < 1:
            raise RuntimeError("--repeats must be at least 1.")

        missing = [model for model in models if model not in set(available)]
        if missing and args.pull_missing:
            pull_missing_models(models, available, host=host)
            available = installed_models(host)
            missing = [model for model in models if model not in set(available)]
        if missing:
            raise RuntimeError(
                "These models are not installed on the selected Ollama server: "
                + ", ".join(missing)
                + ". Use --pull-missing or run 'ollama pull MODEL'."
            )

        model_identities = selected_model_identities(host, models)
        if not args.yes and not args.dry_run and not confirm_plan(models, tasks, repeats):
            print("Cancelled.")
            return

        run_id = args.run_id or default_run_id()
        run_dir = ROOT / "runs" / run_id
        if run_dir.exists():
            raise RuntimeError(
                f"Run directory already exists: {run_dir}. Choose another --run-id or use --resume."
            )
        run_dir.mkdir(parents=True)
        manifest = {
            "schema_version": 2,
            "run_id": run_id,
            "status": "planned" if args.dry_run else "running",
            "created_at": utc_now(),
            "ollama_host": host,
            "provider_or_runtime": "local_ollama",
            "ollama_transport": TRANSPORT_NAME,
            "stream": False,
            "num_ctx": num_ctx,
            "ollama_generation_settings": {
                "num_ctx": num_ctx,
                "think": os.environ.get(
                    "HEPTOOLBENCH_OLLAMA_THINK", "auto"
                ),
                "temperature": os.environ.get(
                    "HEPTOOLBENCH_OLLAMA_TEMPERATURE", "auto"
                ),
                "seed": os.environ.get(
                    "HEPTOOLBENCH_OLLAMA_SEED", "auto"
                ),
                "num_predict": os.environ.get(
                    "HEPTOOLBENCH_OLLAMA_NUM_PREDICT", "auto"
                ),
            },
            "evaluation_order": "model_repeat_task",
            "suite": suite_name,
            "models": models,
            "model_identities": model_identities,
            "tasks": tasks,
            "prompt_sha256_by_task": {
                task_id: sha256_text(build_prompt(task_id))
                for task_id in tasks
            },
            "repeats": repeats,
            "timeout_seconds": timeout,
            "planned_evaluations": len(models) * len(tasks) * repeats,
            "runner_source_sha256": {
                "run_benchmark.py": file_sha256(Path(__file__)),
                "runners/run_ollama_task.py": file_sha256(
                    ROOT / "runners/run_ollama_task.py"
                ),
                "runners/ollama_http_transport.py": file_sha256(
                    ROOT / "runners/ollama_http_transport.py"
                ),
            },
        }
        write_manifest(run_dir / "run_manifest.json", manifest)

    planned = len(models) * len(tasks) * repeats
    print("\nHEPToolBench local evaluation\n=============================")
    print(f"Run ID:      {run_id}")
    print(f"Ollama host: {host}")
    print(f"Transport:   {TRANSPORT_NAME}")
    print(f"num_ctx:     {num_ctx}")
    print("Order:       model -> repeat -> task")
    print(f"Models:      {len(models)}")
    print(f"Tasks:       {len(tasks)}")
    print(f"Repeats:     {repeats}")
    print(f"Evaluations: {planned}")
    print(f"Run folder:  {run_dir}")

    if args.dry_run:
        print("\nDry run: no model calls were made.")
        return

    completed = 0
    skipped = 0

    try:
        for model in models:
            for repeat in range(1, repeats + 1):
                for task_id in tasks:
                    result_path = result_path_for(run_dir, model, task_id, repeat)
                    if valid_result(result_path):
                        skipped += 1
                        completed += 1
                        print(f"[skip {completed}/{planned}] {model} | {task_id} | repeat={repeat}")
                        continue

                    print(f"\n[run {completed + 1}/{planned}] {model} | {task_id} | repeat={repeat}")
                    result = run_attempt(
                        run_dir=run_dir,
                        run_id=run_id,
                        model=model,
                        task_id=task_id,
                        repeat=repeat,
                        timeout=timeout,
                        host=host,
                        num_ctx=num_ctx,
                    )
                    completed += 1
                    print(f"[score] score={result.get('score')} passed={result.get('passed')}")
                    if result.get("valid_for_scoring") is not True:
                        manifest = load_manifest(run_dir)
                        manifest["status"] = "stopped_infrastructure_error"
                        manifest["stopped_at"] = utc_now()
                        manifest["completed_evaluations"] = completed
                        manifest["last_invalid_result"] = relative_to_root(
                            result_path
                        )
                        write_manifest(run_dir / "run_manifest.json", manifest)
                        raise RuntimeError(
                            "Infrastructure-invalid output was rejected before "
                            f"scoring. See {result_path}. Fix the route, then "
                            f"resume with ./run_benchmark.sh --resume {run_id}."
                        )
                    rebuild_outputs(quiet=True)

        rebuild_outputs(quiet=False)
        audit = audit_run_integrity(
            run_dir=run_dir,
            models=models,
            tasks=tasks,
            repeats=repeats,
            model_identities=model_identities,
        )
        manifest = load_manifest(run_dir)
        manifest["status"] = (
            "completed_verified"
            if audit["passed"]
            else "completed_integrity_failed"
        )
        manifest["completed_at"] = utc_now()
        manifest["completed_evaluations"] = completed
        manifest["skipped_existing"] = skipped
        manifest["integrity_audit"] = "integrity_audit.json"
        write_manifest(run_dir / "run_manifest.json", manifest)
        if not audit["passed"]:
            raise RuntimeError(
                "The run finished, but its integrity audit failed. Do not use "
                f"the scores; inspect {run_dir / 'integrity_audit.json'}."
            )

    except KeyboardInterrupt:
        manifest = load_manifest(run_dir)
        manifest["status"] = "interrupted"
        manifest["interrupted_at"] = utc_now()
        manifest["completed_evaluations"] = completed
        manifest["skipped_existing"] = skipped
        write_manifest(run_dir / "run_manifest.json", manifest)
        rebuild_outputs(quiet=False)
        print("\nInterrupted safely.")
        print(f"Resume with: ./run_benchmark.sh --resume {run_id}")
        raise SystemExit(130)

    print("\nBenchmark complete\n==================")
    print(f"Per-run CSV:   {run_dir / 'individual_scores.csv'}")
    print(f"Score matrix:  {run_dir / 'score_matrix.csv'}")
    print(f"Integrity:     {run_dir / 'integrity_audit.json'} (PASS)")
    print(f"Model summary: {run_dir / 'summary_by_model.csv'}")
    print(f"Task summary:  {run_dir / 'summary_by_task.csv'}")
    print(f"All-runs CSV:  {ROOT / 'results' / 'all_runs_long.csv'}")


if __name__ == "__main__":
    main()
