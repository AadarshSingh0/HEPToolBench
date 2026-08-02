#!/usr/bin/env python3
"""Score Task017: scan recovery / rerun planning."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


EXPECTED_KEYS = {
    "status",
    "scan_parameter",
    "total_intended_points",
    "completed_points_gev",
    "failed_points_gev",
    "missing_points_gev",
    "points_to_rerun_gev",
    "number_of_reruns",
    "rerun_run_directories",
    "safe_to_make_final_plot",
    "recommended_action",
}


def strip_ansi_and_controls(text: str) -> tuple[str, bool]:
    original = text
    # Remove ANSI escape sequences and common terminal cursor-control artifacts.
    text = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", text)
    text = text.replace("\x1b", "")
    # Apply backspaces locally.
    while "\b" in text:
        text = re.sub(r".?\x08", "", text, count=1)
    # Remove common chat/reasoning sentinels without deleting JSON content.
    text = re.sub(r"</?think>", "", text, flags=re.IGNORECASE)
    text = text.replace("<|endoftext|>", "").replace("<|im_start|>", "").replace("<|im_end|>", "")
    # Drop remaining non-printing controls except whitespace.
    text = "".join(ch for ch in text if ch in "\n\r\t" or ord(ch) >= 32)
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
    seen = set()
    unique = []
    for cand in candidates:
        if cand not in seen:
            unique.append(cand)
            seen.add(cand)
    return unique


def try_load_json(attempt: str) -> Any | None:
    try:
        return json.loads(attempt)
    except Exception:
        try:
            return json.loads(repair_newlines_inside_strings(attempt))
        except Exception:
            return None


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

    no_fence = remove_markdown_fences(cleaned).strip()
    repaired = repair_newlines_inside_strings(no_fence).strip()
    attempts = [cleaned.strip(), no_fence, repaired]
    attempts.extend(balanced_json_candidates(repaired))

    best: dict[str, Any] | None = None
    best_score = -1
    best_attempt = ""
    for attempt in attempts:
        if not attempt:
            continue
        obj = try_load_json(attempt)
        if isinstance(obj, dict):
            score = len(EXPECTED_KEYS.intersection(obj.keys()))
            # Prefer the object with the most expected keys; break ties by longer object.
            score2 = score * 100000 + len(attempt)
            if score2 > best_score:
                best = obj
                best_score = score2
                best_attempt = attempt

    if best is not None:
        flags["parseable_json"] = True
        try:
            flags["strict_json_only"] = json.dumps(json.loads(cleaned), sort_keys=True) == json.dumps(best, sort_keys=True)
        except Exception:
            flags["strict_json_only"] = False
            flags["includes_explanation_not_json_only"] = True
        # Also mark explanation if the best object was extracted from surrounding text.
        if not flags["strict_json_only"] and best_attempt.strip() != cleaned.strip():
            flags["includes_explanation_not_json_only"] = True
        return best, flags
    return None, flags


def as_float(x: Any) -> float | None:
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        # Accept forms such as "2.5 GeV" and run labels such as "run_mS_2p5".
        s = x.replace("p", ".") if re.search(r"\d+p\d", x) else x
        m = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", s)
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
        s = x.strip().lower().replace("_", " ")
        if s in {"true", "yes", "safe", "complete", "completed"}:
            return True
        if s in {"false", "no", "not safe", "unsafe", "incomplete", "not complete"}:
            return False
    return None


def float_list(values: Any) -> list[float]:
    if values is None:
        return []
    if not isinstance(values, list):
        values = [values]
    out: list[float] = []
    for item in values:
        val = as_float(item)
        if val is not None:
            out.append(round(val, 6))
    return out


def list_close_set(values: Any, expected: list[float], tol: float = 1e-6) -> bool:
    got = sorted(float_list(values))
    exp = sorted(round(x, 6) for x in expected)
    if len(got) != len(exp):
        return False
    return all(abs(a - b) <= tol for a, b in zip(got, exp))


def contains_no_extra_rerun(values: Any) -> bool:
    got = sorted(float_list(values))
    return got == [2.0, 2.5]


def normalize_text(s: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def list_contains_dir(values: Any, target: str) -> bool:
    if values is None:
        return False
    if not isinstance(values, list):
        values = [values]
    target_norm = normalize_text(target)
    for item in values:
        txt = normalize_text(item)
        if target_norm in txt:
            return True
    return False


def score_object(obj: dict[str, Any] | None, flags: dict[str, bool]) -> dict[str, Any]:
    checks = {
        "parseable_json": flags.get("parseable_json", False),
        "strict_json_only": flags.get("strict_json_only", False),
        "status_rerun_required": False,
        "scan_parameter_correct": False,
        "total_intended_points_correct": False,
        "completed_points_correct": False,
        "failed_points_correct": False,
        "missing_points_correct": False,
        "points_to_rerun_correct": False,
        "number_of_reruns_correct": False,
        "rerun_directories_correct": False,
        "safe_to_make_final_plot_false": False,
        "recommended_action_mentions_rerun_before_plot": False,
    }
    normalized = None

    if obj is not None:
        status_norm = str(obj.get("status", "")).strip().lower().replace("-", "_").replace(" ", "_")
        scan_parameter_norm = normalize_text(obj.get("scan_parameter", ""))
        rec_action = str(obj.get("recommended_action", "")).lower()
        checks.update(
            {
                "status_rerun_required": status_norm in {"rerun_required", "incomplete", "partial", "recovery_required"},
                "scan_parameter_correct": scan_parameter_norm in {"ms", "m_s", "scalarmass", "mass", "s_mass", "msgev"},
                "total_intended_points_correct": as_int(obj.get("total_intended_points")) == 5,
                "completed_points_correct": list_close_set(obj.get("completed_points_gev"), [1.0, 1.5, 3.0]),
                "failed_points_correct": list_close_set(obj.get("failed_points_gev"), [2.0]),
                "missing_points_correct": list_close_set(obj.get("missing_points_gev"), [2.5]),
                "points_to_rerun_correct": contains_no_extra_rerun(obj.get("points_to_rerun_gev")),
                "number_of_reruns_correct": as_int(obj.get("number_of_reruns")) == 2,
                "rerun_directories_correct": list_contains_dir(obj.get("rerun_run_directories"), "run_mS_2p0") and list_contains_dir(obj.get("rerun_run_directories"), "run_mS_2p5"),
                "safe_to_make_final_plot_false": normalize_bool(obj.get("safe_to_make_final_plot")) is False,
                "recommended_action_mentions_rerun_before_plot": ("rerun" in rec_action or "repeat" in rec_action) and ("plot" in rec_action or "final" in rec_action or "table" in rec_action),
            }
        )
        normalized = {
            "status": status_norm or None,
            "scan_parameter": obj.get("scan_parameter"),
            "total_intended_points": as_int(obj.get("total_intended_points")),
            "completed_points_gev": float_list(obj.get("completed_points_gev")),
            "failed_points_gev": float_list(obj.get("failed_points_gev")),
            "missing_points_gev": float_list(obj.get("missing_points_gev")),
            "points_to_rerun_gev": float_list(obj.get("points_to_rerun_gev")),
            "number_of_reruns": as_int(obj.get("number_of_reruns")),
            "safe_to_make_final_plot": normalize_bool(obj.get("safe_to_make_final_plot")),
        }

    weights = {
        "parseable_json": 0.05,
        "status_rerun_required": 0.08,
        "scan_parameter_correct": 0.05,
        "total_intended_points_correct": 0.08,
        "completed_points_correct": 0.12,
        "failed_points_correct": 0.10,
        "missing_points_correct": 0.10,
        "points_to_rerun_correct": 0.15,
        "number_of_reruns_correct": 0.08,
        "rerun_directories_correct": 0.06,
        "safe_to_make_final_plot_false": 0.08,
        "recommended_action_mentions_rerun_before_plot": 0.05,
    }
    assert abs(sum(weights.values()) - 1.0) < 1e-12
    score = sum(weight for key, weight in weights.items() if checks.get(key))
    if checks["parseable_json"] and not checks["strict_json_only"]:
        score = min(score, 0.97)

    passed = (
        checks["parseable_json"]
        and checks["status_rerun_required"]
        and checks["total_intended_points_correct"]
        and checks["completed_points_correct"]
        and checks["failed_points_correct"]
        and checks["missing_points_correct"]
        and checks["points_to_rerun_correct"]
        and checks["number_of_reruns_correct"]
        and checks["safe_to_make_final_plot_false"]
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
        "task_id": "scan_recovery_017",
        "checks": checks,
        "normalized_recovery_plan": normalized,
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
