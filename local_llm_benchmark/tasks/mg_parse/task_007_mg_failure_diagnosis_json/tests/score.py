#!/usr/bin/env python3
"""Score mg_parse_007 submissions."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


EXPECTED = {
    "status": "failed",
    "process": "p p > t tbar",
    "error_type": "invalid_antiparticle_syntax",
    "offending_line": "generate p p > t tbar",
    "expected_line": "generate p p > t t~",
    "fix": "replace tbar with t~ in the generate line",
}


def extract_json(raw: str) -> tuple[dict | None, list[str]]:
    failures = []
    text = raw.strip()
    try:
        return json.loads(text), failures
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json|text)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        failures.append("includes_markdown_fence")
        try:
            return json.loads(fence.group(1)), failures
        except json.JSONDecodeError:
            failures.append("invalid_json_inside_markdown")

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        failures.append("includes_explanation_not_json_only")
        try:
            return json.loads(raw[start : end + 1]), failures
        except json.JSONDecodeError:
            failures.append("invalid_json_substring")

    failures.append("not_parseable_json")
    return None, failures


def norm(value) -> str:
    return str(value).strip()


def norm_lower(value) -> str:
    return norm(value).lower()


def score_submission(path: Path) -> dict:
    raw = path.read_text()
    data, failures = extract_json(raw)

    checks = {
        "parseable_json": data is not None,
        "strict_json_only": False,
        "status_failed": False,
        "process_correct": False,
        "error_type_correct": False,
        "offending_line_correct": False,
        "expected_line_correct": False,
        "fix_correct": False,
    }

    normalized = None
    if data is not None:
        checks["strict_json_only"] = not failures
        status = norm_lower(data.get("status", ""))
        process = norm(data.get("process", ""))
        error_type = norm_lower(data.get("error_type", ""))
        offending_line = norm(data.get("offending_line", ""))
        expected_line = norm(data.get("expected_line", ""))
        fix = norm_lower(data.get("fix", ""))

        checks["status_failed"] = status == EXPECTED["status"]
        checks["process_correct"] = process == EXPECTED["process"]
        checks["error_type_correct"] = error_type == EXPECTED["error_type"]
        checks["offending_line_correct"] = offending_line == EXPECTED["offending_line"]
        checks["expected_line_correct"] = expected_line == EXPECTED["expected_line"]
        checks["fix_correct"] = (
            "replace" in fix
            and "tbar" in fix
            and "t~" in fix
            and "generate line" in fix
        )

        normalized = {
            "status": status,
            "process": process,
            "error_type": error_type,
            "offending_line": offending_line,
            "expected_line": expected_line,
            "fix": fix,
        }

        failure_map = {
            "status_failed": "wrong_status",
            "process_correct": "wrong_process",
            "error_type_correct": "wrong_error_type",
            "offending_line_correct": "wrong_offending_line",
            "expected_line_correct": "wrong_expected_line",
            "fix_correct": "wrong_fix",
        }
        for check, failure in failure_map.items():
            if not checks[check]:
                failures.append(failure)

    weights = {
        "parseable_json": 0.20,
        "strict_json_only": 0.05,
        "status_failed": 0.10,
        "process_correct": 0.12,
        "error_type_correct": 0.18,
        "offending_line_correct": 0.15,
        "expected_line_correct": 0.15,
        "fix_correct": 0.05,
    }
    score = sum(weight for key, weight in weights.items() if checks[key])

    passed = (
        checks["parseable_json"]
        and checks["status_failed"]
        and checks["process_correct"]
        and checks["error_type_correct"]
        and checks["offending_line_correct"]
        and checks["expected_line_correct"]
        and checks["fix_correct"]
    )
    strict_passed = passed and checks["strict_json_only"]

    return {
        "task_id": "mg_parse_007",
        "score": round(score, 3),
        "passed": passed,
        "strict_passed": strict_passed,
        "checks": checks,
        "failure_modes": sorted(set(failures)),
        "normalized_diagnosis": normalized,
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
