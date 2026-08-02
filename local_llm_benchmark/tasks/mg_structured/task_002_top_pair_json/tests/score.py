#!/usr/bin/env python3
"""Score mg_structured_002 submissions."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from runners.structured_mg_builder import build_proc_card, params_from_dict


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


def norm_state(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(x).strip() for x in value]


def score_submission(path: Path) -> dict:
    raw = path.read_text()
    data, failures = extract_json(raw)

    checks = {
        "parseable_json": data is not None,
        "strict_json_only": False,
        "model_sm": False,
        "initial_state_pp": False,
        "final_state_ttbar": False,
        "beam_energy_6500": False,
        "output_dir_ttbar": False,
        "nevents_10000": False,
        "builder_generates_valid_card": False,
    }

    generated_card = None
    normalized = None

    if data is not None:
        checks["strict_json_only"] = not failures
        model = str(data.get("model", "")).strip().lower()
        initial = norm_state(data.get("initial_state"))
        output_dir = str(data.get("output_dir", "")).strip()

        checks["model_sm"] = model in {"sm", "standard model"}
        checks["initial_state_pp"] = initial == ["p", "p"]

        try:
            params = params_from_dict(data)
            checks["final_state_ttbar"] = Counter(params.final_state) == Counter(["t", "t~"])
            generated_card = build_proc_card(params)
            checks["builder_generates_valid_card"] = (
                "generate p p > t t~" in generated_card
                and "output TTbar" in generated_card
                and "set ebeam1 6500" in generated_card
                and "set ebeam2 6500" in generated_card
            )
            normalized = {
                "model": params.model,
                "initial_state": params.initial_state,
                "final_state": params.final_state,
                "beam_energy_gev": params.beam_energy_gev,
                "output_dir": params.output_dir,
                "nevents": params.nevents,
            }
        except Exception as exc:
            failures.append(f"builder_error:{type(exc).__name__}")

        try:
            checks["beam_energy_6500"] = float(data.get("beam_energy_gev")) == 6500.0
        except (TypeError, ValueError):
            checks["beam_energy_6500"] = False

        checks["output_dir_ttbar"] = output_dir == "TTbar"
        try:
            checks["nevents_10000"] = int(data.get("nevents", 10000)) == 10000
        except (TypeError, ValueError):
            checks["nevents_10000"] = False

    if data is not None:
        if not checks["model_sm"]:
            failures.append("wrong_model")
        if not checks["initial_state_pp"]:
            failures.append("wrong_initial_state")
        if not checks["final_state_ttbar"]:
            failures.append("wrong_final_state")
        if not checks["beam_energy_6500"]:
            failures.append("wrong_beam_energy")
        if not checks["output_dir_ttbar"]:
            failures.append("wrong_output_dir")
        if not checks["nevents_10000"]:
            failures.append("wrong_nevents")
        if not checks["builder_generates_valid_card"]:
            failures.append("builder_did_not_generate_expected_card")

    weights = {
        "parseable_json": 0.20,
        "strict_json_only": 0.05,
        "model_sm": 0.10,
        "initial_state_pp": 0.15,
        "final_state_ttbar": 0.20,
        "beam_energy_6500": 0.20,
        "output_dir_ttbar": 0.05,
        "nevents_10000": 0.025,
        "builder_generates_valid_card": 0.025,
    }
    score = sum(weight for key, weight in weights.items() if checks[key])
    passed = (
        checks["parseable_json"]
        and checks["model_sm"]
        and checks["initial_state_pp"]
        and checks["final_state_ttbar"]
        and checks["beam_energy_6500"]
        and checks["builder_generates_valid_card"]
    )
    strict_passed = passed and checks["strict_json_only"]

    return {
        "task_id": "mg_structured_002",
        "score": round(score, 3),
        "passed": passed,
        "strict_passed": strict_passed,
        "checks": checks,
        "failure_modes": sorted(set(failures)),
        "submission": str(path),
        "normalized_params": normalized,
        "generated_proc_card": generated_card,
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

