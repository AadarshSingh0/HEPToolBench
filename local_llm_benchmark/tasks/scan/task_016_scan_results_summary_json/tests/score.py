#!/usr/bin/env python3
"""Score Task016: parameter-scan result table summary."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any


def strip_ansi_and_controls(text: str) -> tuple[str, bool]:
    original = text
    # ANSI CSI and common terminal cursor/control sequences.
    text = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", text)
    text = text.replace("\x1b", "")
    # Remove common chat/reasoning sentinels without deleting JSON content.
    text = re.sub(r"</?think>", "", text, flags=re.IGNORECASE)
    text = text.replace("<|endoftext|>", "").replace("<|im_start|>", "").replace("<|im_end|>", "")
    return text, text != original


def remove_markdown_fences(text: str) -> str:
    text = re.sub(r"```(?:json|text)?", "", text, flags=re.IGNORECASE)
    return text.replace("```", "")


def repair_newlines_inside_strings(text: str) -> str:
    out: list[str] = []
    in_str = False
    escape = False
    for ch in text:
        if in_str:
            if escape:
                out.append(ch)
                escape = False
            elif ch == "\\":
                out.append(ch)
                escape = True
            elif ch == '"':
                out.append(ch)
                in_str = False
            elif ch in "\n\r\t":
                out.append(" ")
            else:
                out.append(ch)
        else:
            out.append(ch)
            if ch == '"':
                in_str = True
    return "".join(out)


def balanced_json_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    starts = [i for i, ch in enumerate(text) if ch == "{"]
    for start in starts:
        depth = 0
        in_str = False
        escape = False
        for j in range(start, len(text)):
            ch = text[j]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidates.append(text[start : j + 1])
                        break
    # Prefer larger objects later during best-candidate scoring, but remove duplicates.
    seen = set()
    unique = []
    for cand in candidates:
        if cand not in seen:
            unique.append(cand)
            seen.add(cand)
    return unique


def try_parse_json(text: str) -> tuple[dict[str, Any] | None, dict[str, bool]]:
    flags = {
        "strict_json_only": False,
        "includes_markdown_fence": "```" in text,
        "includes_explanation_not_json_only": False,
        "terminal_artifacts_removed": False,
        "parseable_json": False,
    }
    cleaned, changed = strip_ansi_and_controls(text.strip())
    flags["terminal_artifacts_removed"] = changed

    attempts = []
    attempts.append(cleaned.strip())
    attempts.append(remove_markdown_fences(cleaned).strip())
    attempts.append(repair_newlines_inside_strings(remove_markdown_fences(cleaned)).strip())
    attempts.extend(balanced_json_candidates(repair_newlines_inside_strings(remove_markdown_fences(cleaned))))

    best: dict[str, Any] | None = None
    best_score = -1
    expected_keys = {
        "status",
        "scan_parameter",
        "total_points",
        "successful_points",
        "failed_points",
        "failed_masses_gev",
        "failed_run_directories",
        "max_cross_section_mass_gev",
        "max_cross_section_pb",
        "min_successful_cross_section_mass_gev",
        "min_successful_cross_section_pb",
        "monotonic_decreasing_successful_points",
        "rerun_required",
        "recommended_action",
    }
    for attempt in attempts:
        if not attempt:
            continue
        try:
            obj = json.loads(attempt)
        except Exception:
            try:
                obj = json.loads(repair_newlines_inside_strings(attempt))
            except Exception:
                continue
        if isinstance(obj, dict):
            score = len(expected_keys.intersection(obj.keys()))
            if score > best_score:
                best = obj
                best_score = score
                flags["strict_json_only"] = attempt.strip() == cleaned.strip() and cleaned.strip().startswith("{") and cleaned.strip().endswith("}")

    if best is not None:
        flags["parseable_json"] = True
        # If there is text outside the best object, it is not strict JSON only.
        canonical = json.dumps(best, sort_keys=True)
        try:
            if json.dumps(json.loads(cleaned), sort_keys=True) == canonical:
                flags["strict_json_only"] = True
        except Exception:
            flags["includes_explanation_not_json_only"] = True
            flags["strict_json_only"] = False
        return best, flags
    return None, flags


def as_float(x: Any) -> float | None:
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        m = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", x)
        if m:
            try:
                return float(m.group(0))
            except Exception:
                return None
    return None


def as_int(x: Any) -> int | None:
    val = as_float(x)
    if val is None:
        return None
    if abs(val - round(val)) < 1e-9:
        return int(round(val))
    return None


def normalize_bool(x: Any) -> bool | None:
    if isinstance(x, bool):
        return x
    if isinstance(x, str):
        s = x.strip().lower()
        if s in {"true", "yes", "required", "needed"}:
            return True
        if s in {"false", "no", "not required", "not_needed", "not needed"}:
            return False
    return None


def list_contains_float(values: Any, target: float, tol: float = 1e-6) -> bool:
    if not isinstance(values, list):
        values = [values]
    for item in values:
        val = as_float(item)
        if val is not None and abs(val - target) <= tol:
            return True
    return False


def list_contains_text(values: Any, needle: str) -> bool:
    if not isinstance(values, list):
        values = [values]
    needle_norm = re.sub(r"[^a-z0-9]", "", needle.lower())
    for item in values:
        txt = re.sub(r"[^a-z0-9]", "", str(item).lower())
        if needle_norm in txt:
            return True
    return False


def close(x: Any, target: float, tol: float = 1e-3) -> bool:
    val = as_float(x)
    return val is not None and abs(val - target) <= tol


def score_object(obj: dict[str, Any] | None, flags: dict[str, bool]) -> dict[str, Any]:
    checks = {
        "parseable_json": flags.get("parseable_json", False),
        "strict_json_only": flags.get("strict_json_only", False),
        "status_incomplete": False,
        "scan_parameter_correct": False,
        "total_points_correct": False,
        "successful_points_correct": False,
        "failed_points_correct": False,
        "failed_mass_correct": False,
        "failed_run_directory_correct": False,
        "max_cross_section_mass_correct": False,
        "max_cross_section_value_correct": False,
        "min_successful_cross_section_mass_correct": False,
        "min_successful_cross_section_value_correct": False,
        "monotonic_decreasing_correct": False,
        "rerun_required_true": False,
        "recommended_action_mentions_rerun_failed_point": False,
    }
    normalized = None
    if obj is not None:
        status = str(obj.get("status", "")).strip().lower()
        scan_parameter = re.sub(r"[^a-z0-9]", "", str(obj.get("scan_parameter", "")).strip().lower())
        rec_action = str(obj.get("recommended_action", "")).lower()
        checks.update(
            {
                "status_incomplete": status == "incomplete",
                "scan_parameter_correct": scan_parameter in {"ms", "m_s", "mass", "scalarmass", "scalar_mass", "msgev"},
                "total_points_correct": as_int(obj.get("total_points")) == 5,
                "successful_points_correct": as_int(obj.get("successful_points")) == 4,
                "failed_points_correct": as_int(obj.get("failed_points")) == 1,
                "failed_mass_correct": list_contains_float(obj.get("failed_masses_gev"), 2.0),
                "failed_run_directory_correct": list_contains_text(obj.get("failed_run_directories"), "run_mS_2p0"),
                "max_cross_section_mass_correct": close(obj.get("max_cross_section_mass_gev"), 1.0),
                "max_cross_section_value_correct": close(obj.get("max_cross_section_pb"), 12.40),
                "min_successful_cross_section_mass_correct": close(obj.get("min_successful_cross_section_mass_gev"), 3.0),
                "min_successful_cross_section_value_correct": close(obj.get("min_successful_cross_section_pb"), 1.70),
                "monotonic_decreasing_correct": normalize_bool(obj.get("monotonic_decreasing_successful_points")) is True,
                "rerun_required_true": normalize_bool(obj.get("rerun_required")) is True,
                "recommended_action_mentions_rerun_failed_point": ("rerun" in rec_action or "repeat" in rec_action) and ("2.0" in rec_action or "failed" in rec_action or "run_ms_2p0" in rec_action.replace(" ", "_")),
            }
        )
        normalized = {
            "status": status or None,
            "scan_parameter": obj.get("scan_parameter"),
            "total_points": as_int(obj.get("total_points")),
            "successful_points": as_int(obj.get("successful_points")),
            "failed_points": as_int(obj.get("failed_points")),
            "failed_masses_gev": obj.get("failed_masses_gev"),
            "max_cross_section_mass_gev": as_float(obj.get("max_cross_section_mass_gev")),
            "max_cross_section_pb": as_float(obj.get("max_cross_section_pb")),
            "min_successful_cross_section_mass_gev": as_float(obj.get("min_successful_cross_section_mass_gev")),
            "min_successful_cross_section_pb": as_float(obj.get("min_successful_cross_section_pb")),
            "monotonic_decreasing_successful_points": normalize_bool(obj.get("monotonic_decreasing_successful_points")),
            "rerun_required": normalize_bool(obj.get("rerun_required")),
        }

    weights = {
        "parseable_json": 0.05,
        "status_incomplete": 0.08,
        "scan_parameter_correct": 0.05,
        "total_points_correct": 0.08,
        "successful_points_correct": 0.08,
        "failed_points_correct": 0.08,
        "failed_mass_correct": 0.10,
        "failed_run_directory_correct": 0.05,
        "max_cross_section_mass_correct": 0.08,
        "max_cross_section_value_correct": 0.08,
        "min_successful_cross_section_mass_correct": 0.05,
        "min_successful_cross_section_value_correct": 0.05,
        "monotonic_decreasing_correct": 0.08,
        "rerun_required_true": 0.05,
        "recommended_action_mentions_rerun_failed_point": 0.04,
    }
    assert abs(sum(weights.values()) - 1.0) < 1e-12
    score = sum(weight for key, weight in weights.items() if checks.get(key))
    # Formatting issues get a small penalty but do not destroy semantic score.
    if checks["parseable_json"] and not checks["strict_json_only"]:
        score = min(score, 0.97)

    passed = (
        checks["parseable_json"]
        and checks["status_incomplete"]
        and checks["total_points_correct"]
        and checks["successful_points_correct"]
        and checks["failed_points_correct"]
        and checks["failed_mass_correct"]
        and checks["max_cross_section_mass_correct"]
        and checks["max_cross_section_value_correct"]
        and checks["min_successful_cross_section_mass_correct"]
        and checks["min_successful_cross_section_value_correct"]
        and checks["monotonic_decreasing_correct"]
        and checks["rerun_required_true"]
    )

    failure_modes: list[str] = []
    if not checks["parseable_json"]:
        failure_modes.append("not_parseable_json")
    if flags.get("includes_markdown_fence"):
        failure_modes.append("includes_markdown_fence")
    if flags.get("includes_explanation_not_json_only"):
        failure_modes.append("includes_explanation_not_json_only")
    if flags.get("terminal_artifacts_removed"):
        failure_modes.append("terminal_artifacts_removed")
    if checks["parseable_json"]:
        for key, ok in checks.items():
            if key in {"parseable_json", "strict_json_only"}:
                continue
            if not ok:
                failure_modes.append(key.replace("_correct", "_wrong"))

    return {
        "task_id": "scan_results_016",
        "checks": checks,
        "normalized_summary": normalized,
        "score": round(score, 4),
        "passed": bool(passed),
        "strict_passed": bool(passed and checks["strict_json_only"]),
        "failure_modes": failure_modes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    text = args.submission.read_text(errors="replace")
    obj, flags = try_parse_json(text)
    result = score_object(obj, flags)
    result["submission"] = str(args.submission)

    output_text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(output_text, end="")
    if args.output:
        args.output.write_text(output_text)


if __name__ == "__main__":
    main()
