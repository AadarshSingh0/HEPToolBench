#!/usr/bin/env python3
"""Score pythia_config_010 submissions."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ANSI_RE = re.compile("\x1b\\[[0-?]*[ -/]*[@-~]")

EXPECTED = {
    "status": "invalid",
    "number_of_events": 10000,
    "seed_fixed": True,
    "seed_value": 42,
    "isr_enabled": True,
    "fsr_enabled": True,
    "mpi_enabled": False,
    "hadronization_enabled": True,
    "hepmc_output_enabled": True,
    "missing_setting": "PartonLevel:MPI = on",
    "wrong_setting": "PartonLevel:MPI = off",
    "failure_stage": "parton_level",
}


def strip_terminal_artifacts(raw: str) -> str:
    text = ANSI_RE.sub("", raw)
    return "".join(ch for ch in text if ch in "\n\r\t" or ord(ch) >= 32)


def repair_string_newlines(text: str) -> str:
    out = []
    in_string = False
    escaped = False
    for ch in text:
        if in_string and ch in "\n\r":
            out.append(" ")
            escaped = False
            continue
        out.append(ch)
        if escaped:
            escaped = False
        elif ch == "\\" and in_string:
            escaped = True
        elif ch == '"':
            in_string = not in_string
    return "".join(out)


def loads_repaired(candidate: str) -> dict | None:
    try:
        value = json.loads(repair_string_newlines(candidate.strip()))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def balanced_json_candidates(text: str) -> list[str]:
    candidates = []
    for start, char in enumerate(text):
        if char != "{":
            continue
        in_string = False
        escaped = False
        depth = 0
        for index in range(start, len(text)):
            ch = text[index]
            if escaped:
                escaped = False
                continue
            if ch == "\\" and in_string:
                escaped = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start : index + 1])
                    break
    return candidates


def extract_json(raw: str) -> tuple[dict | None, list[str]]:
    failures = []
    text = strip_terminal_artifacts(raw)
    data = loads_repaired(text)
    if data is not None:
        return data, failures

    fence = re.search(r"```(?:json|text)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        failures.append("includes_markdown_fence")
        data = loads_repaired(fence.group(1))
        if data is not None:
            return data, failures
        failures.append("invalid_json_inside_markdown")

    for candidate in reversed(balanced_json_candidates(text)):
        failures.append("includes_explanation_not_json_only")
        data = loads_repaired(candidate)
        if data is not None:
            return data, failures
    if "{" in text and "}" in text:
        failures.append("invalid_json_substring")

    failures.append("not_parseable_json")
    return None, failures


def as_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def as_bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "on", "enabled"}:
            return True
        if lowered in {"false", "no", "off", "disabled"}:
            return False
    return None


def normalized_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value]
    if isinstance(value, str):
        return [value.strip()]
    return []


def contains_setting(settings: list[str], expected: str) -> bool:
    expected_norm = re.sub(r"\s+", "", expected).lower()
    return any(re.sub(r"\s+", "", item).lower() == expected_norm for item in settings)


def score_submission(path: Path) -> dict:
    raw = path.read_text()
    data, failures = extract_json(raw)

    checks = {
        "parseable_json": data is not None,
        "strict_json_only": False,
        "status_invalid": False,
        "number_of_events_correct": False,
        "seed_fixed": False,
        "seed_value_correct": False,
        "isr_enabled": False,
        "fsr_enabled": False,
        "mpi_detected_off": False,
        "hadronization_enabled": False,
        "hepmc_output_enabled": False,
        "missing_mpi_fix_listed": False,
        "failure_stage_parton_level": False,
        "recommended_fix_mentions_mpi": False,
    }

    normalized = None
    if data is not None:
        checks["strict_json_only"] = not failures
        status = str(data.get("status", "")).strip().lower()
        number_of_events = as_int(data.get("number_of_events"))
        seed_fixed = as_bool(data.get("seed_fixed"))
        seed_value = as_int(data.get("seed_value"))
        isr_enabled = as_bool(data.get("isr_enabled"))
        fsr_enabled = as_bool(data.get("fsr_enabled"))
        mpi_enabled = as_bool(data.get("mpi_enabled"))
        hadronization_enabled = as_bool(data.get("hadronization_enabled"))
        hepmc_output_enabled = as_bool(data.get("hepmc_output_enabled"))
        missing_or_wrong_settings = normalized_list(data.get("missing_or_wrong_settings"))
        failure_stage = str(data.get("failure_stage", "")).strip().lower()
        recommended_fix = str(data.get("recommended_fix", "")).strip().lower()

        checks["status_invalid"] = status == EXPECTED["status"]
        checks["number_of_events_correct"] = number_of_events == EXPECTED["number_of_events"]
        checks["seed_fixed"] = seed_fixed is EXPECTED["seed_fixed"]
        checks["seed_value_correct"] = seed_value == EXPECTED["seed_value"]
        checks["isr_enabled"] = isr_enabled is EXPECTED["isr_enabled"]
        checks["fsr_enabled"] = fsr_enabled is EXPECTED["fsr_enabled"]
        checks["mpi_detected_off"] = mpi_enabled is EXPECTED["mpi_enabled"]
        checks["hadronization_enabled"] = hadronization_enabled is EXPECTED["hadronization_enabled"]
        checks["hepmc_output_enabled"] = hepmc_output_enabled is EXPECTED["hepmc_output_enabled"]
        checks["missing_mpi_fix_listed"] = (
            contains_setting(missing_or_wrong_settings, EXPECTED["missing_setting"])
            or contains_setting(missing_or_wrong_settings, EXPECTED["wrong_setting"])
        )
        checks["failure_stage_parton_level"] = failure_stage == EXPECTED["failure_stage"]
        checks["recommended_fix_mentions_mpi"] = (
            "partonlevel:mpi" in recommended_fix.replace(" ", "")
            or "mpi" in recommended_fix
        )

        normalized = {
            "status": status,
            "number_of_events": number_of_events,
            "seed_fixed": seed_fixed,
            "seed_value": seed_value,
            "isr_enabled": isr_enabled,
            "fsr_enabled": fsr_enabled,
            "mpi_enabled": mpi_enabled,
            "hadronization_enabled": hadronization_enabled,
            "hepmc_output_enabled": hepmc_output_enabled,
            "missing_or_wrong_settings": missing_or_wrong_settings,
            "failure_stage": failure_stage,
            "recommended_fix": recommended_fix,
        }

        failure_map = {
            "status_invalid": "wrong_status",
            "number_of_events_correct": "wrong_number_of_events",
            "seed_fixed": "wrong_seed_fixed",
            "seed_value_correct": "wrong_seed_value",
            "isr_enabled": "wrong_isr_setting",
            "fsr_enabled": "wrong_fsr_setting",
            "mpi_detected_off": "missed_mpi_off",
            "hadronization_enabled": "wrong_hadronization_setting",
            "hepmc_output_enabled": "wrong_hepmc_output_setting",
            "missing_mpi_fix_listed": "missing_or_wrong_mpi_fix",
            "failure_stage_parton_level": "wrong_failure_stage",
            "recommended_fix_mentions_mpi": "missing_mpi_recommended_fix",
        }
        for check, failure in failure_map.items():
            if not checks[check]:
                failures.append(failure)

    weights = {
        "parseable_json": 0.10,
        "strict_json_only": 0.03,
        "status_invalid": 0.08,
        "number_of_events_correct": 0.07,
        "seed_fixed": 0.06,
        "seed_value_correct": 0.06,
        "isr_enabled": 0.06,
        "fsr_enabled": 0.06,
        "mpi_detected_off": 0.14,
        "hadronization_enabled": 0.06,
        "hepmc_output_enabled": 0.06,
        "missing_mpi_fix_listed": 0.10,
        "failure_stage_parton_level": 0.06,
        "recommended_fix_mentions_mpi": 0.06,
    }
    score = sum(weight for key, weight in weights.items() if checks[key])

    passed = (
        checks["parseable_json"]
        and checks["status_invalid"]
        and checks["number_of_events_correct"]
        and checks["seed_fixed"]
        and checks["seed_value_correct"]
        and checks["isr_enabled"]
        and checks["fsr_enabled"]
        and checks["mpi_detected_off"]
        and checks["hadronization_enabled"]
        and checks["hepmc_output_enabled"]
        and checks["missing_mpi_fix_listed"]
        and checks["failure_stage_parton_level"]
    )
    strict_passed = passed and checks["strict_json_only"]

    return {
        "task_id": "pythia_config_010",
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
