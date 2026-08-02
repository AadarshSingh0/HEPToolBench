#!/usr/bin/env python3
"""Score lhe_sanity_012 submissions."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ANSI_RE = re.compile("\x1b\\[[0-?]*[ -/]*[@-~]")

EXPECTED = {
    "status": "incomplete",
    "process": "p p > h j",
    "event_file": "Events/run_03/unweighted_events.lhe.gz",
    "requested_events": 10000,
    "observed_events": 9820,
    "missing_events": 180,
    "cross_section_pb": 2.345,
    "cross_section_uncertainty_pb": 0.012,
    "negative_weight_events": 0,
    "negative_weight_fraction": 0.0,
    "failure_stage": "event_count_validation",
}


def strip_terminal_artifacts(raw: str) -> str:
    text = ANSI_RE.sub("", raw)
    text = re.sub(r"\x1b\].*?(?:\x07|\x1b\\\\)", "", text, flags=re.DOTALL)
    buffer: list[str] = []
    for ch in text:
        if ch == "\b":
            if buffer:
                buffer.pop()
            continue
        buffer.append(ch)
    return "".join(ch for ch in "".join(buffer) if ch in "\n\r\t" or ord(ch) >= 32)


def repair_string_newlines(text: str) -> str:
    out: list[str] = []
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
    for start, ch0 in enumerate(text):
        if ch0 != "{":
            continue
        depth = 0
        in_string = False
        escaped = False
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


def parse_value_by_key(text: str, key: str):
    pattern = re.compile(r'"' + re.escape(key) + r'"\s*:\s*', re.IGNORECASE)
    matches = list(pattern.finditer(text))
    if not matches:
        return None
    tail = repair_string_newlines(text[matches[-1].end():]).lstrip()
    if tail.startswith('"'):
        escaped = False
        chars = []
        for ch in tail[1:]:
            if escaped:
                chars.append(ch)
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == '"':
                return "".join(chars).strip()
            chars.append(ch)
        return "".join(chars).strip()
    if tail.startswith('['):
        end = tail.find(']')
        if end >= 0:
            try:
                return json.loads(repair_string_newlines(tail[: end + 1]))
            except Exception:
                return [m.group(1) for m in re.finditer(r'"([^"\\]*(?:\\.[^"\\]*)*)"', tail[: end + 1])]

    # Terminal cursor-control artifacts can split values, e.g.
    #   true -> tru\ntrue
    #   2.345 -> 2.\n2.345
    # Keep a slightly larger chunk and recover the final recognizable literal.
    chunk_match = re.match(r'([^,}]+)', tail, flags=re.DOTALL)
    if not chunk_match:
        return None
    chunk = chunk_match.group(1).strip()
    compact = re.sub(r"\s+", "", chunk).lower()
    if "true" in compact and "false" not in compact:
        return True
    if "false" in compact and "true" not in compact:
        return False
    if compact.startswith('null'):
        return None
    nums = re.findall(r'[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?', chunk)
    if nums:
        # Prefer the last complete number; cursor artifacts often leave a
        # truncated prefix before the true value.
        s = nums[-1]
        return float(s) if any(c in s for c in '.eE') else int(s)
    return chunk.strip()


def salvage_known_fields(raw: str) -> dict | None:
    text = strip_terminal_artifacts(raw)
    keys = [
        "status", "process", "process_correct", "event_file", "file_present",
        "requested_events", "observed_events", "event_count_matches", "missing_events",
        "cross_section_pb", "cross_section_uncertainty_pb", "negative_weight_events",
        "negative_weight_fraction", "failure_stage", "recommended_action",
    ]
    recovered = {}
    for key in keys:
        value = parse_value_by_key(text, key)
        if value is not None:
            recovered[key] = value
    required = {"status", "process", "requested_events", "observed_events", "event_count_matches"}
    if required.issubset(recovered):
        return recovered
    return None


def extract_json(raw: str) -> tuple[dict | None, list[str]]:
    failures: list[str] = []
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
    salvaged = salvage_known_fields(raw)
    if salvaged is not None:
        failures.append("recovered_from_corrupted_json")
        return salvaged, failures

    failures.append("not_parseable_json")
    return None, failures


def norm_process(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def as_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "pass", "passed", "correct"}:
            return True
        if lowered in {"false", "no", "fail", "failed", "incorrect"}:
            return False
    return None


def close(value: float | None, expected: float, tol: float = 1e-9) -> bool:
    return value is not None and abs(value - expected) <= tol


def mentions_event_count(action: str) -> bool:
    text = action.lower()
    return any(word in text for word in ["event", "9820", "10000", "rerun", "generation", "count"])


def score_submission(path: Path) -> dict:
    raw = path.read_text(errors="replace")
    data, failures = extract_json(raw)

    checks = {
        "parseable_json": data is not None,
        "strict_json_only": False,
        "status_incomplete": False,
        "process_correct": False,
        "process_flag_correct": False,
        "event_file_correct": False,
        "file_present": False,
        "requested_events_correct": False,
        "observed_events_correct": False,
        "event_count_mismatch_reported": False,
        "missing_events_correct": False,
        "cross_section_correct": False,
        "cross_section_uncertainty_correct": False,
        "negative_weight_events_correct": False,
        "negative_weight_fraction_correct": False,
        "failure_stage_event_count": False,
        "recommended_action_mentions_event_count": False,
    }

    normalized = None
    if data is not None:
        checks["strict_json_only"] = not failures
        status = str(data.get("status", "")).strip().lower()
        process = norm_process(data.get("process"))
        process_correct_flag = as_bool(data.get("process_correct"))
        event_file = str(data.get("event_file", "")).strip()
        file_present = as_bool(data.get("file_present"))
        requested_events = as_int(data.get("requested_events"))
        observed_events = as_int(data.get("observed_events"))
        event_count_matches = as_bool(data.get("event_count_matches"))
        missing_events = as_int(data.get("missing_events"))
        cross_section = as_float(data.get("cross_section_pb"))
        cross_section_unc = as_float(data.get("cross_section_uncertainty_pb"))
        neg_events = as_int(data.get("negative_weight_events"))
        neg_fraction = as_float(data.get("negative_weight_fraction"))
        failure_stage = str(data.get("failure_stage", "")).strip().lower()
        recommended_action = str(data.get("recommended_action", "")).strip().lower()

        # Some models report negative_weight_fraction as a percent string; accept 0 either way.
        checks["status_incomplete"] = status in {"incomplete", "invalid", "failed"}
        checks["process_correct"] = process == EXPECTED["process"]
        checks["process_flag_correct"] = process_correct_flag is True
        checks["event_file_correct"] = event_file == EXPECTED["event_file"]
        checks["file_present"] = file_present is True
        checks["requested_events_correct"] = requested_events == EXPECTED["requested_events"]
        checks["observed_events_correct"] = observed_events == EXPECTED["observed_events"]
        checks["event_count_mismatch_reported"] = event_count_matches is False
        checks["missing_events_correct"] = missing_events == EXPECTED["missing_events"]
        checks["cross_section_correct"] = close(cross_section, EXPECTED["cross_section_pb"])
        checks["cross_section_uncertainty_correct"] = close(cross_section_unc, EXPECTED["cross_section_uncertainty_pb"])
        checks["negative_weight_events_correct"] = neg_events == EXPECTED["negative_weight_events"]
        checks["negative_weight_fraction_correct"] = close(neg_fraction, EXPECTED["negative_weight_fraction"], tol=1e-12)
        checks["failure_stage_event_count"] = failure_stage in {"event_count_validation", "lhe_validation", "event_generation"}
        checks["recommended_action_mentions_event_count"] = mentions_event_count(recommended_action)

        normalized = {
            "status": status,
            "process": process,
            "process_correct": process_correct_flag,
            "event_file": event_file,
            "file_present": file_present,
            "requested_events": requested_events,
            "observed_events": observed_events,
            "event_count_matches": event_count_matches,
            "missing_events": missing_events,
            "cross_section_pb": cross_section,
            "cross_section_uncertainty_pb": cross_section_unc,
            "negative_weight_events": neg_events,
            "negative_weight_fraction": neg_fraction,
            "failure_stage": failure_stage,
            "recommended_action": recommended_action,
        }

        failure_map = {
            "status_incomplete": "wrong_status",
            "process_correct": "wrong_process",
            "process_flag_correct": "wrong_process_correct_flag",
            "event_file_correct": "wrong_event_file",
            "file_present": "wrong_file_present",
            "requested_events_correct": "wrong_requested_events",
            "observed_events_correct": "wrong_observed_events",
            "event_count_mismatch_reported": "missed_event_count_mismatch",
            "missing_events_correct": "wrong_missing_events",
            "cross_section_correct": "wrong_cross_section",
            "cross_section_uncertainty_correct": "wrong_cross_section_uncertainty",
            "negative_weight_events_correct": "wrong_negative_weight_events",
            "negative_weight_fraction_correct": "wrong_negative_weight_fraction",
            "failure_stage_event_count": "wrong_failure_stage",
            "recommended_action_mentions_event_count": "weak_recommended_action",
        }
        for check, failure in failure_map.items():
            if not checks[check]:
                failures.append(failure)

    weights = {
        "parseable_json": 0.07,
        "strict_json_only": 0.03,
        "status_incomplete": 0.07,
        "process_correct": 0.07,
        "process_flag_correct": 0.04,
        "event_file_correct": 0.05,
        "file_present": 0.05,
        "requested_events_correct": 0.06,
        "observed_events_correct": 0.08,
        "event_count_mismatch_reported": 0.10,
        "missing_events_correct": 0.08,
        "cross_section_correct": 0.06,
        "cross_section_uncertainty_correct": 0.05,
        "negative_weight_events_correct": 0.04,
        "negative_weight_fraction_correct": 0.04,
        "failure_stage_event_count": 0.06,
        "recommended_action_mentions_event_count": 0.05,
    }
    assert abs(sum(weights.values()) - 1.0) < 1e-12
    score = sum(weight for key, weight in weights.items() if checks[key])

    required_for_pass = [
        "parseable_json",
        "status_incomplete",
        "process_correct",
        "event_file_correct",
        "file_present",
        "requested_events_correct",
        "observed_events_correct",
        "event_count_mismatch_reported",
        "missing_events_correct",
        "cross_section_correct",
        "cross_section_uncertainty_correct",
        "negative_weight_events_correct",
        "negative_weight_fraction_correct",
        "failure_stage_event_count",
        "recommended_action_mentions_event_count",
    ]
    passed = all(checks[key] for key in required_for_pass)
    strict_passed = passed and checks["strict_json_only"]

    return {
        "task_id": "lhe_sanity_012",
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
