#!/usr/bin/env python3
"""Score Task014 parameter-scan planning JSON submissions."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

EXPECTED_VALUES = [round(1.0 + 0.5 * i, 10) for i in range(19)]

WEIGHTS = {
    "parseable_json": 0.05,
    "status_valid": 0.05,
    "process_correct": 0.08,
    "scan_parameter_correct": 0.08,
    "start_correct": 0.06,
    "stop_correct": 0.06,
    "step_correct": 0.06,
    "inclusive_endpoints_true": 0.04,
    "number_of_points_correct": 0.10,
    "scan_values_correct": 0.14,
    "fixed_coupling_correct": 0.08,
    "nevents_correct": 0.05,
    "beam_energy_correct": 0.04,
    "modifies_param_card": 0.06,
    "collects_outputs": 0.05,
}

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-12


def strip_ansi_and_control(text: str) -> str:
    """Remove common terminal control artifacts from Ollama/TTY output."""
    text = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", text)
    text = re.sub(r"\x1b[@-_][0-?]*[ -/]*[@-~]", "", text)
    text = text.replace("\x08", "")
    text = text.replace("\r", "")
    return text


def remove_markdown_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json|JSON|text)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def balanced_json_objects(text: str) -> list[str]:
    """Return all balanced JSON-looking objects in text, not only the first one.

    Reasoning-model outputs sometimes contain small JSON fragments in the
    explanation before the final answer.  We therefore parse all candidates and
    later keep the one that best matches the task schema.
    """
    objects: list[str] = []
    starts = [m.start() for m in re.finditer(r"\{", text)]
    for start in starts:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        objects.append(text[start : i + 1])
                        break
    # Keep order but remove duplicates.
    seen: set[str] = set()
    unique: list[str] = []
    for obj in objects:
        if obj not in seen:
            unique.append(obj)
            seen.add(obj)
    return unique


def first_balanced_json_object(text: str) -> str | None:
    objs = balanced_json_objects(text)
    return objs[0] if objs else None


def replace_newlines_inside_strings(text: str) -> str:
    out: list[str] = []
    in_string = False
    escape = False
    for ch in text:
        if in_string:
            if escape:
                out.append(ch)
                escape = False
            elif ch == "\\":
                out.append(ch)
                escape = True
            elif ch == '"':
                out.append(ch)
                in_string = False
            elif ch in "\n\t":
                out.append(" ")
            else:
                out.append(ch)
        else:
            out.append(ch)
            if ch == '"':
                in_string = True
    return "".join(out)


def repair_terminal_artifact_duplicates(text: str) -> str:
    """Repair common cursor-control damage after ANSI stripping.

    Ollama/TTY output can leave duplicated fragments such as ``6.0\n6.0,``
    after removing cursor-left escape sequences.  When the adjacent duplicated
    numeric token is identical, collapse it to one token.  This is conservative:
    it does not turn genuinely different numbers into a valid list.
    """
    text = re.sub(
        r"(?<![\d.])([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s+\1(?=\s*[,\]])",
        r"\1",
        text,
    )
    # Duplicated word fragments sometimes appear in strings after cursor edits.
    text = re.sub(r"\b([A-Za-z_]{3,})\s+\1\b", r"\1", text)
    return text


def remove_unscored_per_point_actions_if_broken(text: str) -> str:
    """Drop per_point_actions if terminal artifacts make that unscored field invalid.

    The benchmark does not score this field.  We should not reject an otherwise
    correct scan plan only because a cursor artifact split a string inside this
    optional list.
    """
    return re.sub(
        r',\s*"per_point_actions"\s*:\s*\[[\s\S]*?\](?=\s*,\s*"outputs_to_collect")',
        '',
        text,
        flags=re.MULTILINE,
    )


def schema_score_hint(data: dict[str, Any]) -> int:
    """Heuristic used only to choose among multiple parsed JSON objects."""
    keys = {str(k).lower() for k in data.keys()}
    expected = {
        "status", "process", "scan_parameter", "scan_values_gev",
        "start_gev", "stop_gev", "step_gev", "inclusive_endpoints",
        "number_of_points", "fixed_parameters", "beam_energy_gev",
        "nevents", "files_to_modify", "outputs_to_collect",
    }
    return len(keys & expected)


def parse_json_lenient(text: str) -> tuple[dict[str, Any] | None, list[str], str | None]:
    """Parse JSON while tolerating wrappers, markdown fences, and terminal artifacts."""
    failure_modes: list[str] = []
    raw = text
    cleaned = strip_ansi_and_control(raw)
    cleaned = repair_terminal_artifact_duplicates(cleaned)

    strict_json_only = cleaned.strip().startswith("{") and cleaned.strip().endswith("}")
    if "```" in raw:
        failure_modes.append("includes_markdown_fence")
        strict_json_only = False
    if cleaned.strip() != raw.strip() and "terminal_artifacts_removed" not in failure_modes:
        failure_modes.append("terminal_artifacts_removed")
        strict_json_only = False

    # Explanation/wrapper detection: use the best/largest final object, not a
    # small object embedded in reasoning text.
    objects = balanced_json_objects(cleaned)
    if not strict_json_only:
        if objects:
            # Choose the object with the most task-schema keys for wrapper checks.
            obj_for_wrap = max(objects, key=lambda o: len(o))
            before = cleaned.split(obj_for_wrap, 1)[0].strip()
            after_obj = cleaned.split(obj_for_wrap, 1)[1].strip()
            if before or after_obj:
                failure_modes.append("includes_explanation_not_json_only")
        else:
            if cleaned.strip():
                failure_modes.append("includes_explanation_not_json_only")

    candidates: list[str] = []
    candidates.append(cleaned.strip())
    candidates.append(remove_markdown_fences(cleaned))
    candidates.extend(objects)
    # Prefer later/larger objects too, because reasoning text may contain tiny
    # JSON fragments before the final answer.
    candidates.extend(sorted(objects, key=len, reverse=True))

    parsed: list[tuple[int, dict[str, Any]]] = []
    for cand in candidates:
        if not cand:
            continue
        base_repairs = [cand]
        base_repairs.append(remove_unscored_per_point_actions_if_broken(cand))
        repairs: list[str] = []
        for base in base_repairs:
            repairs.extend([
                base,
                re.sub(r",\s*([}\]])", r"\1", base),
                replace_newlines_inside_strings(base),
                re.sub(r",\s*([}\]])", r"\1", replace_newlines_inside_strings(base)),
            ])
        for repaired in repairs:
            try:
                data = json.loads(repaired)
                if isinstance(data, dict):
                    parsed.append((schema_score_hint(data), data))
            except Exception:
                pass

    if parsed:
        parsed.sort(key=lambda item: item[0], reverse=True)
        return parsed[0][1], sorted(set(failure_modes)), strict_json_only and not failure_modes

    failure_modes.append("not_parseable_json")
    return None, sorted(set(failure_modes)), None


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", value)
        if match:
            try:
                return float(match.group(0))
            except ValueError:
                return None
    return None


def as_int(value: Any) -> int | None:
    f = as_float(value)
    if f is None:
        return None
    if abs(f - round(f)) < 1e-9:
        return int(round(f))
    return None


def norm_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9+~>]+", "", str(value).lower())


def nearly_equal(a: Any, b: float, tol: float = 1e-6) -> bool:
    f = as_float(a)
    return f is not None and abs(f - b) <= tol


def get_any(data: dict[str, Any], keys: list[str]) -> Any:
    lowered = {str(k).lower(): v for k, v in data.items()}
    for key in keys:
        if key in data:
            return data[key]
        if key.lower() in lowered:
            return lowered[key.lower()]
    return None


def get_fixed_coupling(data: dict[str, Any]) -> Any:
    fixed = get_any(data, ["fixed_parameters", "fixed_params", "constant_parameters"])
    if isinstance(fixed, dict):
        for key, val in fixed.items():
            nk = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if nk in {"gs", "g_s", "couplinggs", "scalarcoupling", "g"}:
                return val
    # Also tolerate flat schemas.
    return get_any(data, ["gS", "gs", "fixed_gS", "coupling", "coupling_gS"])


def listify(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        # Try extracting a bracketless numeric list from strings.
        nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", value)
        if len(nums) > 1:
            return [float(x) for x in nums]
        return [value]
    if value is None:
        return []
    return [value]


def scan_values_correct(data: dict[str, Any]) -> bool:
    values = get_any(data, ["scan_values_gev", "scan_values", "mass_values_gev", "points", "grid"])
    vals = listify(values)
    numeric = [as_float(v) for v in vals]
    numeric = [v for v in numeric if v is not None]
    if len(numeric) != len(EXPECTED_VALUES):
        return False
    return all(abs(a - b) < 1e-6 for a, b in zip(numeric, EXPECTED_VALUES))


def contains_token(items: Any, required_fragments: list[str]) -> bool:
    text = " ".join(str(x) for x in listify(items)).lower()
    # For param-card checks, accept both the literal filename and the
    # common phrase "model parameter card".  These are semantically the
    # same target artifact in this benchmark.
    if required_fragments == ["param_card"]:
        compact = re.sub(r"[^a-z0-9_]+", "_", text)
        return "param_card" in compact or ("parameter" in text and "card" in text)
    return all(fragment.lower() in text for fragment in required_fragments)


def output_collects(data: dict[str, Any]) -> bool:
    outputs = get_any(data, ["outputs_to_collect", "collect", "outputs", "results_to_collect"])
    text = " ".join(str(x) for x in listify(outputs)).lower()
    has_xsec = "cross" in text and ("section" in text or "xsec" in text) and "pb" in text
    has_run_dir = ("run" in text and "dir" in text) or "directory" in text
    return has_xsec and has_run_dir


def score_submission(text: str, submission: str) -> dict[str, Any]:
    data, failure_modes, strict_json_only = parse_json_lenient(text)
    checks = {key: False for key in WEIGHTS}
    normalized_plan = None

    if data is not None:
        checks["parseable_json"] = True
        status = str(get_any(data, ["status"]) or "").lower()
        checks["status_valid"] = "valid" in status and "invalid" not in status

        process = get_any(data, ["process", "process_string", "madgraph_process"])
        checks["process_correct"] = norm_text(process) == norm_text("p p > S > e+ e-")

        scan_parameter = get_any(data, ["scan_parameter", "parameter", "mass_parameter", "scanned_parameter"])
        checks["scan_parameter_correct"] = re.sub(r"[^a-z0-9]", "", str(scan_parameter).lower()) in {
            "ms", "masss", "mediatormass", "m_s"
        }

        checks["start_correct"] = nearly_equal(get_any(data, ["start_gev", "start", "scan_start_gev", "min_gev"]), 1.0)
        checks["stop_correct"] = nearly_equal(get_any(data, ["stop_gev", "stop", "scan_stop_gev", "max_gev"]), 10.0)
        checks["step_correct"] = nearly_equal(get_any(data, ["step_gev", "step", "scan_step_gev", "spacing_gev"]), 0.5)
        checks["inclusive_endpoints_true"] = bool(get_any(data, ["inclusive_endpoints", "inclusive", "include_endpoints"])) is True
        checks["number_of_points_correct"] = as_int(get_any(data, ["number_of_points", "n_points", "num_points", "nscan"])) == 19
        checks["scan_values_correct"] = scan_values_correct(data)
        checks["fixed_coupling_correct"] = nearly_equal(get_fixed_coupling(data), 0.1)
        checks["nevents_correct"] = as_int(get_any(data, ["nevents", "number_of_events", "events_per_point"])) == 10000
        checks["beam_energy_correct"] = nearly_equal(get_any(data, ["beam_energy_gev", "ebeam_gev", "ebeam", "beam_energy_per_beam_gev"]), 6500.0)
        checks["modifies_param_card"] = contains_token(get_any(data, ["files_to_modify", "files", "modified_files"]), ["param_card"])
        checks["collects_outputs"] = output_collects(data)

        normalized_plan = {
            "status": status or None,
            "process": process,
            "scan_parameter": scan_parameter,
            "start_gev": as_float(get_any(data, ["start_gev", "start", "scan_start_gev", "min_gev"])),
            "stop_gev": as_float(get_any(data, ["stop_gev", "stop", "scan_stop_gev", "max_gev"])),
            "step_gev": as_float(get_any(data, ["step_gev", "step", "scan_step_gev", "spacing_gev"])),
            "number_of_points": as_int(get_any(data, ["number_of_points", "n_points", "num_points", "nscan"])),
            "beam_energy_gev": as_float(get_any(data, ["beam_energy_gev", "ebeam_gev", "ebeam", "beam_energy_per_beam_gev"])),
            "nevents": as_int(get_any(data, ["nevents", "number_of_events", "events_per_point"])),
        }

    score = round(sum(weight for key, weight in WEIGHTS.items() if checks[key]), 4)

    critical = [
        "parseable_json",
        "status_valid",
        "process_correct",
        "scan_parameter_correct",
        "start_correct",
        "stop_correct",
        "step_correct",
        "inclusive_endpoints_true",
        "number_of_points_correct",
        "fixed_coupling_correct",
        "nevents_correct",
        "beam_energy_correct",
        "modifies_param_card",
        "collects_outputs",
    ]
    passed = all(checks[key] for key in critical) and score >= 0.85

    if not checks["scan_values_correct"] and data is not None:
        failure_modes.append("wrong_or_missing_scan_values")
    if data is not None and not checks["number_of_points_correct"]:
        failure_modes.append("wrong_number_of_scan_points")
    if data is not None and not checks["beam_energy_correct"]:
        failure_modes.append("wrong_or_missing_beam_energy")
    if data is not None and not checks["fixed_coupling_correct"]:
        failure_modes.append("wrong_or_missing_fixed_coupling")

    return {
        "task_id": "scan_plan_014",
        "submission": submission,
        "checks": checks,
        "score": score,
        "passed": passed,
        "strict_passed": bool(strict_json_only) and passed,
        "failure_modes": sorted(set(failure_modes)),
        "normalized_plan": normalized_plan,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = score_submission(args.submission.read_text(errors="replace"), str(args.submission))
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
