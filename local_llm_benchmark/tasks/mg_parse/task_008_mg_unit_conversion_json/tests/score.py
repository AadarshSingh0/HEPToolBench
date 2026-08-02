#!/usr/bin/env python3
"""Score mg_parse_008 submissions."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


EXPECTED = {
    "status": "success",
    "process": "p p > h j",
    "cross_section_pb": 2.345,
    "cross_section_uncertainty_pb": 0.012,
    "input_unit": "fb",
    "output_unit": "pb",
    "nevents": 5000,
    "event_file": "Events/run_02/unweighted_events.lhe.gz",
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


def as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def close(value: float | None, expected: float) -> bool:
    return value is not None and abs(value - expected) <= 1e-12


def score_submission(path: Path) -> dict:
    raw = path.read_text()
    data, failures = extract_json(raw)

    checks = {
        "parseable_json": data is not None,
        "strict_json_only": False,
        "status_success": False,
        "process_correct": False,
        "cross_section_converted_to_pb": False,
        "uncertainty_converted_to_pb": False,
        "input_unit_fb": False,
        "output_unit_pb": False,
        "nevents_correct": False,
        "event_file_correct": False,
    }

    normalized = None
    if data is not None:
        checks["strict_json_only"] = not failures
        status = str(data.get("status", "")).strip().lower()
        process = str(data.get("process", "")).strip()
        input_unit = str(data.get("input_unit", "")).strip().lower()
        output_unit = str(data.get("output_unit", "")).strip().lower()
        event_file = str(data.get("event_file", "")).strip()
        cross_section = as_float(data.get("cross_section_pb"))
        uncertainty = as_float(data.get("cross_section_uncertainty_pb"))
        nevents = as_int(data.get("nevents"))

        checks["status_success"] = status == EXPECTED["status"]
        checks["process_correct"] = process == EXPECTED["process"]
        checks["cross_section_converted_to_pb"] = close(cross_section, EXPECTED["cross_section_pb"])
        checks["uncertainty_converted_to_pb"] = close(uncertainty, EXPECTED["cross_section_uncertainty_pb"])
        checks["input_unit_fb"] = input_unit == EXPECTED["input_unit"]
        checks["output_unit_pb"] = output_unit == EXPECTED["output_unit"]
        checks["nevents_correct"] = nevents == EXPECTED["nevents"]
        checks["event_file_correct"] = event_file == EXPECTED["event_file"]

        normalized = {
            "status": status,
            "process": process,
            "cross_section_pb": cross_section,
            "cross_section_uncertainty_pb": uncertainty,
            "input_unit": input_unit,
            "output_unit": output_unit,
            "nevents": nevents,
            "event_file": event_file,
        }

        failure_map = {
            "status_success": "wrong_status",
            "process_correct": "wrong_process",
            "cross_section_converted_to_pb": "wrong_cross_section_or_unit_conversion",
            "uncertainty_converted_to_pb": "wrong_uncertainty_or_unit_conversion",
            "input_unit_fb": "wrong_input_unit",
            "output_unit_pb": "wrong_output_unit",
            "nevents_correct": "wrong_nevents",
            "event_file_correct": "wrong_event_file",
        }
        for check, failure in failure_map.items():
            if not checks[check]:
                failures.append(failure)

    weights = {
        "parseable_json": 0.15,
        "strict_json_only": 0.05,
        "status_success": 0.08,
        "process_correct": 0.12,
        "cross_section_converted_to_pb": 0.22,
        "uncertainty_converted_to_pb": 0.16,
        "input_unit_fb": 0.06,
        "output_unit_pb": 0.06,
        "nevents_correct": 0.05,
        "event_file_correct": 0.05,
    }
    score = sum(weight for key, weight in weights.items() if checks[key])

    passed = (
        checks["parseable_json"]
        and checks["status_success"]
        and checks["process_correct"]
        and checks["cross_section_converted_to_pb"]
        and checks["uncertainty_converted_to_pb"]
        and checks["input_unit_fb"]
        and checks["output_unit_pb"]
        and checks["nevents_correct"]
        and checks["event_file_correct"]
    )
    strict_passed = passed and checks["strict_json_only"]

    return {
        "task_id": "mg_parse_008",
        "score": round(score, 3),
        "passed": passed,
        "strict_passed": strict_passed,
        "checks": checks,
        "failure_modes": sorted(set(failures)),
        "normalized_summary": normalized,
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
