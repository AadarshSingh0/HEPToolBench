#!/usr/bin/env python3
"""Score mg_parse_009 submissions."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ANSI_RE = re.compile("\x1b\\[[0-?]*[ -/]*[@-~]")

EXPECTED = {
    "status": "incomplete",
    "process": "p p > t t~",
    "requested_events": 10000,
    "lhe_present": True,
    "lhe_events": 10000,
    "pythia8_requested": True,
    "pythia8_present": True,
    "pythia8_events": 10000,
    "delphes_requested": True,
    "delphes_present": False,
    "missing_output": "Events/run_01/tag_1_delphes_events.root",
    "event_count_consistent": True,
    "failure_stage": "delphes",
}


def strip_terminal_artifacts(raw: str) -> str:
    text = ANSI_RE.sub("", raw)
    return "".join(ch for ch in text if ch in "\n\r\t" or ord(ch) >= 32)


def repair_string_newlines(text: str) -> str:
    """Replace literal newlines inside JSON strings with spaces.

    Ollama sometimes emits terminal line-clear control codes while wrapping long
    strings. After removing those codes, a literal newline can remain inside a
    quoted JSON value. That is not valid JSON, but the intended value is
    unambiguous and should not erase otherwise correct semantic output.
    """
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
        if lowered in {"true", "yes", "present", "ok"}:
            return True
        if lowered in {"false", "no", "missing", "absent"}:
            return False
    return None


def normalized_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value]
    if isinstance(value, str):
        return [value.strip()]
    return []


def score_submission(path: Path) -> dict:
    raw = path.read_text()
    data, failures = extract_json(raw)

    checks = {
        "parseable_json": data is not None,
        "strict_json_only": False,
        "status_incomplete": False,
        "process_correct": False,
        "requested_events_correct": False,
        "lhe_present": False,
        "lhe_events_correct": False,
        "pythia8_requested": False,
        "pythia8_present": False,
        "pythia8_events_correct": False,
        "delphes_requested": False,
        "delphes_absent": False,
        "missing_delphes_output": False,
        "event_count_consistent": False,
        "failure_stage_delphes": False,
        "recommended_action_mentions_delphes": False,
    }

    normalized = None
    if data is not None:
        checks["strict_json_only"] = not failures
        status = str(data.get("status", "")).strip().lower()
        process = str(data.get("process", "")).strip()
        requested_events = as_int(data.get("requested_events"))
        lhe_present = as_bool(data.get("lhe_present"))
        lhe_events = as_int(data.get("lhe_events"))
        pythia8_requested = as_bool(data.get("pythia8_requested"))
        pythia8_present = as_bool(data.get("pythia8_present"))
        pythia8_events = as_int(data.get("pythia8_events"))
        delphes_requested = as_bool(data.get("delphes_requested"))
        delphes_present = as_bool(data.get("delphes_present"))
        missing_outputs = normalized_list(data.get("missing_outputs"))
        event_count_consistent = as_bool(data.get("event_count_consistent"))
        failure_stage = str(data.get("failure_stage", "")).strip().lower()
        recommended_action = str(data.get("recommended_action", "")).strip().lower()

        checks["status_incomplete"] = status == EXPECTED["status"]
        checks["process_correct"] = process == EXPECTED["process"]
        checks["requested_events_correct"] = requested_events == EXPECTED["requested_events"]
        checks["lhe_present"] = lhe_present is EXPECTED["lhe_present"]
        checks["lhe_events_correct"] = lhe_events == EXPECTED["lhe_events"]
        checks["pythia8_requested"] = pythia8_requested is EXPECTED["pythia8_requested"]
        checks["pythia8_present"] = pythia8_present is EXPECTED["pythia8_present"]
        checks["pythia8_events_correct"] = pythia8_events == EXPECTED["pythia8_events"]
        checks["delphes_requested"] = delphes_requested is EXPECTED["delphes_requested"]
        checks["delphes_absent"] = delphes_present is EXPECTED["delphes_present"]
        checks["missing_delphes_output"] = EXPECTED["missing_output"] in missing_outputs
        checks["event_count_consistent"] = event_count_consistent is EXPECTED["event_count_consistent"]
        checks["failure_stage_delphes"] = failure_stage == EXPECTED["failure_stage"]
        checks["recommended_action_mentions_delphes"] = "delphes" in recommended_action

        normalized = {
            "status": status,
            "process": process,
            "requested_events": requested_events,
            "lhe_present": lhe_present,
            "lhe_events": lhe_events,
            "pythia8_requested": pythia8_requested,
            "pythia8_present": pythia8_present,
            "pythia8_events": pythia8_events,
            "delphes_requested": delphes_requested,
            "delphes_present": delphes_present,
            "missing_outputs": missing_outputs,
            "event_count_consistent": event_count_consistent,
            "failure_stage": failure_stage,
            "recommended_action": recommended_action,
        }

        failure_map = {
            "status_incomplete": "wrong_status",
            "process_correct": "wrong_process",
            "requested_events_correct": "wrong_requested_events",
            "lhe_present": "wrong_lhe_presence",
            "lhe_events_correct": "wrong_lhe_event_count",
            "pythia8_requested": "wrong_pythia8_requested",
            "pythia8_present": "wrong_pythia8_presence",
            "pythia8_events_correct": "wrong_pythia8_event_count",
            "delphes_requested": "wrong_delphes_requested",
            "delphes_absent": "wrong_delphes_presence",
            "missing_delphes_output": "missing_or_wrong_missing_output",
            "event_count_consistent": "wrong_event_count_consistency",
            "failure_stage_delphes": "wrong_failure_stage",
            "recommended_action_mentions_delphes": "missing_delphes_recommended_action",
        }
        for check, failure in failure_map.items():
            if not checks[check]:
                failures.append(failure)

    weights = {
        "parseable_json": 0.10,
        "strict_json_only": 0.03,
        "status_incomplete": 0.07,
        "process_correct": 0.07,
        "requested_events_correct": 0.05,
        "lhe_present": 0.05,
        "lhe_events_correct": 0.05,
        "pythia8_requested": 0.05,
        "pythia8_present": 0.05,
        "pythia8_events_correct": 0.05,
        "delphes_requested": 0.05,
        "delphes_absent": 0.10,
        "missing_delphes_output": 0.08,
        "event_count_consistent": 0.05,
        "failure_stage_delphes": 0.10,
        "recommended_action_mentions_delphes": 0.05,
    }
    score = sum(weight for key, weight in weights.items() if checks[key])

    passed = (
        checks["parseable_json"]
        and checks["status_incomplete"]
        and checks["process_correct"]
        and checks["requested_events_correct"]
        and checks["lhe_present"]
        and checks["lhe_events_correct"]
        and checks["pythia8_requested"]
        and checks["pythia8_present"]
        and checks["pythia8_events_correct"]
        and checks["delphes_requested"]
        and checks["delphes_absent"]
        and checks["missing_delphes_output"]
        and checks["event_count_consistent"]
        and checks["failure_stage_delphes"]
    )
    strict_passed = passed and checks["strict_json_only"]

    return {
        "task_id": "mg_parse_009",
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
