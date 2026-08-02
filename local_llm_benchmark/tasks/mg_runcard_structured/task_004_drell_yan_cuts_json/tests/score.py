#!/usr/bin/env python3
"""Score mg_runcard_structured_004 submissions."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from runners.structured_mg_builder import build_run_card, runcard_params_from_dict


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


def close(value: float | None, expected: float) -> bool:
    return value is not None and abs(value - expected) < 1e-9


def score_submission(path: Path) -> dict:
    raw = path.read_text()
    data, failures = extract_json(raw)

    checks = {
        "parseable_json": data is not None,
        "strict_json_only": False,
        "nevents_10000": False,
        "iseed_42": False,
        "ebeam1_6500": False,
        "ebeam2_6500": False,
        "ptl_20": False,
        "etal_2p5": False,
        "builder_generates_valid_run_card": False,
    }

    normalized = None
    generated_run_card = None

    if data is not None:
        checks["strict_json_only"] = not failures
        try:
            params = runcard_params_from_dict(data)
            checks["nevents_10000"] = params.nevents == 10000
            checks["iseed_42"] = params.iseed == 42
            checks["ebeam1_6500"] = close(params.ebeam1_gev, 6500.0)
            checks["ebeam2_6500"] = close(params.ebeam2_gev, 6500.0)
            checks["ptl_20"] = close(params.ptl_min_gev, 20.0)
            checks["etal_2p5"] = close(params.eta_l_max, 2.5)
            generated_run_card = build_run_card(params)
            checks["builder_generates_valid_run_card"] = all(
                line in generated_run_card
                for line in [
                    "10000 = nevents",
                    "42 = iseed",
                    "6500 = ebeam1",
                    "6500 = ebeam2",
                    "20 = ptl",
                    "2.5 = etal",
                ]
            )
            normalized = {
                "nevents": params.nevents,
                "iseed": params.iseed,
                "ebeam1_gev": params.ebeam1_gev,
                "ebeam2_gev": params.ebeam2_gev,
                "ptl_min_gev": params.ptl_min_gev,
                "eta_l_max": params.eta_l_max,
            }
        except Exception as exc:
            failures.append(f"builder_error:{type(exc).__name__}")

    if data is not None:
        if not checks["nevents_10000"]:
            failures.append("wrong_nevents")
        if not checks["iseed_42"]:
            failures.append("wrong_iseed")
        if not checks["ebeam1_6500"]:
            failures.append("wrong_ebeam1")
        if not checks["ebeam2_6500"]:
            failures.append("wrong_ebeam2")
        if not checks["ptl_20"]:
            failures.append("wrong_ptl")
        if not checks["etal_2p5"]:
            failures.append("wrong_etal")
        if not checks["builder_generates_valid_run_card"]:
            failures.append("builder_did_not_generate_expected_run_card")

    weights = {
        "parseable_json": 0.20,
        "strict_json_only": 0.05,
        "nevents_10000": 0.10,
        "iseed_42": 0.10,
        "ebeam1_6500": 0.12,
        "ebeam2_6500": 0.12,
        "ptl_20": 0.13,
        "etal_2p5": 0.13,
        "builder_generates_valid_run_card": 0.05,
    }
    score = sum(weight for key, weight in weights.items() if checks[key])
    passed = (
        checks["parseable_json"]
        and checks["nevents_10000"]
        and checks["iseed_42"]
        and checks["ebeam1_6500"]
        and checks["ebeam2_6500"]
        and checks["ptl_20"]
        and checks["etal_2p5"]
        and checks["builder_generates_valid_run_card"]
    )
    strict_passed = passed and checks["strict_json_only"]

    return {
        "task_id": "mg_runcard_structured_004",
        "score": round(score, 3),
        "passed": passed,
        "strict_passed": strict_passed,
        "checks": checks,
        "failure_modes": sorted(set(failures)),
        "submission": str(path),
        "normalized_params": normalized,
        "generated_run_card": generated_run_card,
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
