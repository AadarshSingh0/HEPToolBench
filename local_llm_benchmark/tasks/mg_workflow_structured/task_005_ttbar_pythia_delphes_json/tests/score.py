#!/usr/bin/env python3
"""Score mg_workflow_structured_005 submissions."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from runners.structured_mg_builder import build_workflow_script, workflow_params_from_dict


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


def is_off(value: str) -> bool:
    return value.strip().lower() in {"off", "false", "disabled", "disable", "none", "no"}


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
        "output_dir": False,
        "nevents_10000": False,
        "iseed_42": False,
        "shower_pythia8": False,
        "detector_delphes": False,
        "madspin_off": False,
        "builder_generates_valid_workflow": False,
    }

    normalized = None
    generated_script = None

    if data is not None:
        checks["strict_json_only"] = not failures
        model = str(data.get("model", "")).strip().lower()
        initial = norm_state(data.get("initial_state"))

        checks["model_sm"] = model in {"sm", "standard model"}
        checks["initial_state_pp"] = initial == ["p", "p"]

        try:
            params = workflow_params_from_dict(data)
            checks["final_state_ttbar"] = Counter(params.final_state) == Counter(["t", "t~"])
            checks["beam_energy_6500"] = params.beam_energy_gev == 6500.0
            checks["output_dir"] = params.output_dir == "TTbar_P8_Delphes"
            checks["nevents_10000"] = params.nevents == 10000
            checks["iseed_42"] = params.iseed == 42
            checks["shower_pythia8"] = params.shower.lower() == "pythia8"
            checks["detector_delphes"] = params.detector.lower() == "delphes"
            checks["madspin_off"] = is_off(params.madspin)
            generated_script = build_workflow_script(params)
            checks["builder_generates_valid_workflow"] = all(
                line in generated_script
                for line in [
                    "generate p p > t t~",
                    "output TTbar_P8_Delphes",
                    "shower=Pythia8",
                    "detector=Delphes",
                    "analysis=OFF",
                    "madspin=OFF",
                    "done",
                    "set nevents 10000",
                    "set iseed 42",
                    "set ebeam1 6500",
                    "set ebeam2 6500",
                ]
            )
            normalized = {
                "model": params.model,
                "initial_state": params.initial_state,
                "final_state": params.final_state,
                "beam_energy_gev": params.beam_energy_gev,
                "output_dir": params.output_dir,
                "nevents": params.nevents,
                "iseed": params.iseed,
                "shower": params.shower,
                "detector": params.detector,
                "madspin": params.madspin,
            }
        except Exception as exc:
            failures.append(f"builder_error:{type(exc).__name__}")

    if data is not None:
        failure_map = {
            "model_sm": "wrong_model",
            "initial_state_pp": "wrong_initial_state",
            "final_state_ttbar": "wrong_final_state",
            "beam_energy_6500": "wrong_beam_energy",
            "output_dir": "wrong_output_dir",
            "nevents_10000": "wrong_nevents",
            "iseed_42": "wrong_iseed",
            "shower_pythia8": "wrong_shower",
            "detector_delphes": "wrong_detector",
            "madspin_off": "wrong_madspin",
            "builder_generates_valid_workflow": "builder_did_not_generate_expected_workflow",
        }
        for check, failure in failure_map.items():
            if not checks[check]:
                failures.append(failure)

    weights = {
        "parseable_json": 0.15,
        "strict_json_only": 0.04,
        "model_sm": 0.06,
        "initial_state_pp": 0.07,
        "final_state_ttbar": 0.12,
        "beam_energy_6500": 0.10,
        "output_dir": 0.05,
        "nevents_10000": 0.06,
        "iseed_42": 0.05,
        "shower_pythia8": 0.10,
        "detector_delphes": 0.10,
        "madspin_off": 0.06,
        "builder_generates_valid_workflow": 0.04,
    }
    score = sum(weight for key, weight in weights.items() if checks[key])
    passed = (
        checks["parseable_json"]
        and checks["model_sm"]
        and checks["initial_state_pp"]
        and checks["final_state_ttbar"]
        and checks["beam_energy_6500"]
        and checks["nevents_10000"]
        and checks["iseed_42"]
        and checks["shower_pythia8"]
        and checks["detector_delphes"]
        and checks["madspin_off"]
        and checks["builder_generates_valid_workflow"]
    )
    strict_passed = passed and checks["strict_json_only"]

    return {
        "task_id": "mg_workflow_structured_005",
        "score": round(score, 3),
        "passed": passed,
        "strict_passed": strict_passed,
        "checks": checks,
        "failure_modes": sorted(set(failures)),
        "submission": str(path),
        "normalized_params": normalized,
        "generated_mg5_script": generated_script,
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
