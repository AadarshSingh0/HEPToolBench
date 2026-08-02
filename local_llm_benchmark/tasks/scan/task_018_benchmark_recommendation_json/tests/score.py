#!/usr/bin/env python3
"""Score Task018 benchmark recommendation JSON with robust recovery."""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

TASK_ID = "benchmark_recommendation_018"

WEIGHTS = {
    "recoverable_output": 0.05,
    "status_complete": 0.10,
    "scan_parameter_correct": 0.05,
    "safe_to_make_final_plot": 0.10,
    "point_counts_correct": 0.10,
    "usable_masses_correct": 0.10,
    "benchmark_mass_correct": 0.20,
    "benchmark_cross_section_correct": 0.10,
    "selection_rule_correct": 0.10,
    "monotonic_decreasing_correct": 0.05,
    "next_action_correct": 0.05,
}
PASS_THRESHOLD = 0.85

EXPECTED_MASSES = [1.0, 1.5, 2.0, 2.5, 3.0]
EXPECTED_BENCHMARK = 1.5
EXPECTED_SIGMA = 8.10
REQUIRED = {
    "status", "scan_parameter", "safe_to_make_final_plot", "total_points",
    "successful_points", "failed_points", "missing_points", "usable_masses_gev",
    "benchmark_mass_gev", "benchmark_cross_section_pb", "selection_rule",
    "monotonic_decreasing_cross_section", "next_action",
}

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
OSC_RE = re.compile(r"\x1b\].*?(?:\x07|\x1b\\)")

def clean_text(text: str) -> str:
    text = OSC_RE.sub("", text)
    text = ANSI_RE.sub("", text)
    while "\b" in text:
        text = re.sub(r".?\x08", "", text, count=1)
    text = text.replace("\r", "\n")
    text = text.replace("```json", "```").replace("```JSON", "```").replace("```", "")
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    return text.strip()

def norm_text(x: Any) -> str:
    return re.sub(r"[^a-z0-9.]+", " ", str(x).lower()).strip()

def object_quality(obj: Any, required: set[str]) -> int:
    if not isinstance(obj, dict):
        return -100
    score = sum(1 for k in required if k in obj)
    if len(obj) < 4:
        score -= 20
    return score

def parse_json_best(text: str, required: set[str]) -> tuple[Any | None, str]:
    original = text.strip()
    strict_candidate = (
        original.startswith("{")
        and original.endswith("}")
        and "```" not in original
        and not ANSI_RE.search(original)
        and not OSC_RE.search(original)
    )
    cleaned = clean_text(text)
    dec = json.JSONDecoder()
    candidates: list[Any] = []
    try:
        obj = json.loads(cleaned)
        return obj, "strict" if strict_candidate else "recovered_json_substring"
    except Exception:
        pass
    for i, ch in enumerate(cleaned):
        if ch != "{":
            continue
        try:
            obj, _ = dec.raw_decode(cleaned[i:])
            if isinstance(obj, dict):
                candidates.append(obj)
        except Exception:
            continue
    if candidates:
        candidates.sort(key=lambda o: object_quality(o, required), reverse=True)
        return candidates[0], "recovered_json_substring"
    repaired = re.sub(r",\s*([}\]])", r"\1", cleaned)
    for i, ch in enumerate(repaired):
        if ch != "{":
            continue
        try:
            obj, _ = dec.raw_decode(repaired[i:])
            if isinstance(obj, dict):
                candidates.append(obj)
        except Exception:
            continue
    if candidates:
        candidates.sort(key=lambda o: object_quality(o, required), reverse=True)
        return candidates[0], "recovered_after_trailing_comma_repair"
    return None, "not_parseable_json"

def get_number(obj: dict[str, Any], keys: list[str], raw: str = "") -> float | None:
    for k in keys:
        if isinstance(obj, dict) and k in obj:
            v = obj[k]
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                return float(v)
            m = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", str(v))
            if m:
                return float(m.group(0))
    if raw:
        for k in keys:
            pat = re.compile(r'"?'+re.escape(k)+r'"?\s*:\s*"?\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', re.I)
            m = pat.search(raw)
            if m:
                return float(m.group(1))
    return None

def get_bool(obj: dict[str, Any], keys: list[str], raw: str = "") -> bool | None:
    for k in keys:
        if isinstance(obj, dict) and k in obj:
            v = obj[k]
            if isinstance(v, bool):
                return v
            s = norm_text(v)
            if s in {"true", "yes", "safe", "complete", "completed"}:
                return True
            if s in {"false", "no", "unsafe", "incomplete"}:
                return False
    if raw:
        for k in keys:
            m = re.search(r'"?'+re.escape(k)+r'"?\s*:\s*(true|false|yes|no)', raw, re.I)
            if m:
                return m.group(1).lower() in {"true","yes"}
    return None

def get_string(obj: dict[str, Any], keys: list[str], raw: str = "") -> str:
    for k in keys:
        if isinstance(obj, dict) and k in obj:
            return str(obj[k])
    if raw:
        for k in keys:
            # stop at next quoted key if possible
            m = re.search(r'"?'+re.escape(k)+r'"?\s*:\s*"([^"]*)"', raw, re.I|re.S)
            if m:
                return m.group(1)
            m = re.search(r'"?'+re.escape(k)+r'"?\s*:\s*([^,\n}]+)', raw, re.I|re.S)
            if m:
                return m.group(1)
    return ""

def extract_list_from_obj_or_raw(obj: dict[str, Any], keys: list[str], raw: str = "") -> list[float]:
    val = None
    for k in keys:
        if isinstance(obj, dict) and k in obj:
            val = obj[k]
            break
    if val is None and raw:
        for k in keys:
            m = re.search(r'"?'+re.escape(k)+r'"?\s*:\s*\[([^\]]*)\]', raw, re.I|re.S)
            if m:
                val = m.group(1)
                break
    vals: list[float] = []
    if isinstance(val, list):
        items = val
    else:
        items = re.findall(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", str(val or ""))
    for item in items:
        if isinstance(item, bool):
            continue
        if isinstance(item, (int, float)):
            x = float(item)
        else:
            m = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", str(item))
            if not m:
                continue
            x = float(m.group(0))
        if not any(math.isclose(x, y, abs_tol=1e-6) for y in vals):
            vals.append(x)
    return vals

def lists_close(got: list[float], exp: list[float], tol: float = 1e-6) -> bool:
    return len(got) == len(exp) and all(math.isclose(a, b, abs_tol=tol, rel_tol=0) for a, b in zip(got, exp))

def lists_match_set(got: list[float], exp: list[float], tol: float = 1e-6) -> bool:
    return len(got) == len(exp) and all(any(math.isclose(x, y, abs_tol=tol, rel_tol=0) for x in got) for y in exp)


def score_submission(path: Path) -> dict[str, Any]:
    raw0 = path.read_text(errors="replace")
    raw = clean_text(raw0)
    obj, parse_mode = parse_json_best(raw0, REQUIRED)
    strict_json = parse_mode == "strict"
    if obj is None:
        obj = {}

    checks = {k: False for k in WEIGHTS}
    failure_modes: list[str] = []
    normalized: dict[str, Any] = {}

    # If full JSON failed, we still allow semantic field recovery from raw text.
    checks["recoverable_output"] = bool(obj) or ("benchmark_mass_gev" in raw or "benchmark_cross_section_pb" in raw)
    if not checks["recoverable_output"]:
        failure_modes.append(parse_mode)
    elif parse_mode != "strict":
        failure_modes.append(parse_mode)

    status_s = norm_text(get_string(obj, ["status"], raw))
    bad_status = any(w in status_s for w in ["incomplete", "partial", "failed", "missing", "rerun", "not complete"])
    good_status = any(w in status_s for w in ["complete", "completed", "success", "all succeeded", "finished"])
    checks["status_complete"] = good_status and not bad_status
    if not checks["status_complete"]:
        failure_modes.append("status_not_complete")
    normalized["status"] = get_string(obj, ["status"], raw)

    scan_raw = get_string(obj, ["scan_parameter", "parameter"], raw).lower()
    scan_norm = re.sub(r"\bgev\b|\[|\]|\(|\)|/|unit|mass", "", scan_raw)
    scan_norm = re.sub(r"[^a-z0-9]+", "", scan_norm)
    checks["scan_parameter_correct"] = scan_norm == "ms"
    if not checks["scan_parameter_correct"]:
        failure_modes.append("scan_parameter_wrong")
    normalized["scan_parameter"] = scan_raw

    safe = get_bool(obj, ["safe_to_make_final_plot", "safe_to_plot", "final_plot_safe"], raw)
    checks["safe_to_make_final_plot"] = safe is True
    if not checks["safe_to_make_final_plot"]:
        failure_modes.append("safe_to_make_final_plot_wrong")
    normalized["safe_to_make_final_plot"] = safe

    total = get_number(obj, ["total_points", "number_of_points", "n_points"], raw)
    succ = get_number(obj, ["successful_points", "success_points", "n_successful"], raw)
    failed = get_number(obj, ["failed_points", "n_failed"], raw)
    missing = get_number(obj, ["missing_points", "n_missing"], raw)
    checks["point_counts_correct"] = (
        total is not None and succ is not None and failed is not None and missing is not None
        and int(round(total)) == 5 and int(round(succ)) == 5
        and int(round(failed)) == 0 and int(round(missing)) == 0
    )
    if not checks["point_counts_correct"]:
        failure_modes.append("point_counts_wrong")
    normalized.update({"total_points": total, "successful_points": succ, "failed_points": failed, "missing_points": missing})

    masses = extract_list_from_obj_or_raw(obj, ["usable_masses_gev", "usable_masses", "successful_masses_gev", "successful_points_gev"], raw)
    checks["usable_masses_correct"] = lists_match_set(masses, EXPECTED_MASSES)
    if not checks["usable_masses_correct"]:
        failure_modes.append("usable_masses_wrong")
    normalized["usable_masses_gev"] = masses

    bm = get_number(obj, ["benchmark_mass_gev", "selected_mass_gev", "recommended_mass_gev", "benchmark_mass"], raw)
    checks["benchmark_mass_correct"] = bm is not None and math.isclose(bm, EXPECTED_BENCHMARK, abs_tol=1e-6, rel_tol=0)
    if not checks["benchmark_mass_correct"]:
        if bm is not None and math.isclose(bm, 1.0, abs_tol=1e-6, rel_tol=0):
            failure_modes.append("chose_endpoint_maximum_instead_of_interior_benchmark")
        else:
            failure_modes.append("benchmark_mass_wrong")
    normalized["benchmark_mass_gev"] = bm

    sigma = get_number(obj, ["benchmark_cross_section_pb", "selected_cross_section_pb", "recommended_cross_section_pb"], raw)
    checks["benchmark_cross_section_correct"] = sigma is not None and math.isclose(sigma, EXPECTED_SIGMA, abs_tol=1e-3, rel_tol=0)
    if not checks["benchmark_cross_section_correct"]:
        failure_modes.append("benchmark_cross_section_wrong")
    normalized["benchmark_cross_section_pb"] = sigma

    rule = norm_text(get_string(obj, ["selection_rule", "benchmark_selection_rule", "reason"], raw))
    mentions_interior = any(w in rule for w in ["interior", "non endpoint", "nonendpoint", "avoid endpoint", "avoid endpoints", "do not choose endpoint"])
    mentions_largest = any(w in rule for w in ["largest", "maximum", "max", "highest"])
    mentions_success = "success" in rule or "usable" in rule or "valid" in rule
    checks["selection_rule_correct"] = mentions_interior and mentions_largest and mentions_success
    if not checks["selection_rule_correct"]:
        failure_modes.append("selection_rule_incomplete")
    normalized["selection_rule"] = get_string(obj, ["selection_rule", "benchmark_selection_rule", "reason"], raw)

    mono = get_bool(obj, ["monotonic_decreasing_cross_section", "monotonic_decreasing", "cross_section_monotonic_decreasing"], raw)
    checks["monotonic_decreasing_correct"] = mono is True
    if not checks["monotonic_decreasing_correct"]:
        failure_modes.append("monotonic_decreasing_wrong")
    normalized["monotonic_decreasing_cross_section"] = mono

    action_raw = get_string(obj, ["next_action", "recommended_action"], raw)
    action = norm_text(action_raw)
    has_plot = "plot" in action or "scan" in action or "final" in action
    has_detector = "detector" in action or "delphes" in action or "simulation" in action or "analysis" in action
    has_benchmark = "1 5" in action or "1.5" in action_raw or "benchmark" in action
    checks["next_action_correct"] = has_plot and has_detector and has_benchmark
    if not checks["next_action_correct"]:
        failure_modes.append("next_action_incomplete")
    normalized["next_action"] = action_raw

    score = round(sum(WEIGHTS[k] for k, ok in checks.items() if ok), 6)
    passed = score >= PASS_THRESHOLD

    return {
        "task_id": TASK_ID,
        "submission": str(path),
        "score": score,
        "passed": passed,
        "strict_passed": strict_json and passed,
        "checks": checks,
        "failure_modes": failure_modes,
        "normalized_recommendation": normalized,
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = score_submission(args.submission)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")
    print(text)

if __name__ == "__main__":
    main()
