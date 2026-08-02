#!/usr/bin/env python3
"""Score mg_runcard_004 submissions."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


TASK_ID = "mg_runcard_004"
EXPECTED = {
    "nevents": 10000.0,
    "iseed": 42.0,
    "ebeam1": 6500.0,
    "ebeam2": 6500.0,
    "ptl": 20.0,
    "etal": 2.5,
}


def parse_assignments(raw: str) -> dict[str, float]:
    values = {}
    for line in raw.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.match(r"^([0-9.eE+-]+)\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\b", line)
        if not match:
            continue
        try:
            values[match.group(2).lower()] = float(match.group(1))
        except ValueError:
            continue
    return values


def close(value: float | None, expected: float) -> bool:
    return value is not None and abs(value - expected) < 1e-9


def score_submission(path: Path) -> dict:
    raw = path.read_text()
    assignments = parse_assignments(raw)
    failures = []

    checks = {
        "has_run_card_assignments": bool(assignments),
        "nevents_10000": close(assignments.get("nevents"), 10000.0),
        "iseed_42": close(assignments.get("iseed"), 42.0),
        "ebeam1_6500": close(assignments.get("ebeam1"), 6500.0),
        "ebeam2_6500": close(assignments.get("ebeam2"), 6500.0),
        "ptl_20": close(assignments.get("ptl"), 20.0),
        "etal_2p5": close(assignments.get("etal"), 2.5),
        "no_markdown_fence": "```" not in raw,
        "no_set_commands": not re.search(r"^\s*set\s+", raw, re.IGNORECASE | re.MULTILINE),
        "no_process_card_commands": not re.search(
            r"^\s*(import model|define\s+|generate\s+|output\s+|launch\b)",
            raw,
            re.IGNORECASE | re.MULTILINE,
        ),
        "no_long_explanation": not re.search(
            r"following|therefore|Drell-Yan|center-of-mass|run card settings|assignment lines",
            raw,
            re.IGNORECASE,
        ),
    }

    for key, expected in EXPECTED.items():
        if not close(assignments.get(key), expected):
            failures.append(f"wrong_or_missing_{key}")
    if not checks["has_run_card_assignments"]:
        failures.append("no_parseable_run_card_assignments")
    if not checks["no_markdown_fence"]:
        failures.append("includes_markdown_fence")
    if not checks["no_set_commands"]:
        failures.append("uses_set_commands_instead_of_run_card_assignments")
    if not checks["no_process_card_commands"]:
        failures.append("includes_process_card_commands")
    if not checks["no_long_explanation"]:
        failures.append("includes_explanation_not_file_only")

    weights = {
        "has_run_card_assignments": 0.06,
        "nevents_10000": 0.14,
        "iseed_42": 0.12,
        "ebeam1_6500": 0.14,
        "ebeam2_6500": 0.14,
        "ptl_20": 0.14,
        "etal_2p5": 0.14,
        "no_markdown_fence": 0.03,
        "no_set_commands": 0.03,
        "no_process_card_commands": 0.03,
        "no_long_explanation": 0.03,
    }
    score = sum(weight for key, weight in weights.items() if checks[key])

    failure_set = set(failures)
    format_failures = {
        "includes_markdown_fence",
        "uses_set_commands_instead_of_run_card_assignments",
        "includes_process_card_commands",
        "includes_explanation_not_file_only",
    }
    if format_failures.intersection(failure_set):
        score = min(score, 0.70)
    if any(f.startswith("wrong_or_missing_") for f in failures):
        score = min(score, 0.85)

    hard_failures = format_failures | {"no_parseable_run_card_assignments"}
    passed = (
        all(checks[name] for name in [
            "nevents_10000",
            "iseed_42",
            "ebeam1_6500",
            "ebeam2_6500",
            "ptl_20",
            "etal_2p5",
        ])
        and not hard_failures.intersection(failure_set)
    )

    return {
        "task_id": TASK_ID,
        "score": round(score, 3),
        "passed": passed,
        "checks": checks,
        "failure_modes": sorted(set(failures)),
        "parsed_assignments": assignments,
        "submission": str(path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = score_submission(args.submission)
    output = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(output + "\n")
    print(output)


if __name__ == "__main__":
    main()
