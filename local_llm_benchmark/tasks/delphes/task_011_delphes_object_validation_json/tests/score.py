#!/usr/bin/env python3
"""Score delphes_objects_011 submissions."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ANSI_RE = re.compile("\x1b\\[[0-?]*[ -/]*[@-~]")

EXPECTED = {
    "status": "invalid",
    "selected_leptons": 1,
    "electron_count": 1,
    "muon_count": 0,
    "jet_count": 4,
    "b_tagged_jet_count": 1,
    "missing_et_gev": 52.4,
    "lepton_requirement_passed": True,
    "jet_requirement_passed": True,
    "b_tag_requirement_passed": False,
    "met_requirement_passed": True,
    "failure_stage": "object_selection",
}


def strip_terminal_artifacts(raw: str) -> str:
    """Remove common terminal/control artifacts while preserving intended JSON text.

    Ollama/terminal captures can contain ANSI erase/control sequences such as ESC[K,
    carriage returns, or backspace-overwritten characters. These are not model
    semantics, so the scorer strips them before JSON extraction.
    """
    # Remove standard ANSI CSI sequences such as ESC[K, ESC[2K, color codes, etc.
    text = ANSI_RE.sub("", raw)

    # Remove OSC-style terminal sequences, just in case.
    text = re.sub(r"\x1b\].*?(?:\x07|\x1b\\\\)", "", text, flags=re.DOTALL)

    # Apply backspaces literally: delete the previous character.
    buffer = []
    for ch in text:
        if ch == "\b":
            if buffer:
                buffer.pop()
            continue
        buffer.append(ch)
    text = "".join(buffer)

    # Keep only printable characters and whitespace that JSON repair can handle.
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



def parse_value_by_key(text: str, key: str):
    """Best-effort value extraction from JSON-like text damaged by terminal artifacts.

    This is used only after ordinary JSON parsing fails. It extracts the last
    occurrence of a known key from a JSON-like answer. The task still records
    that the answer was not strict JSON.
    """
    pattern = re.compile(r'"' + re.escape(key) + r'"\s*:\s*', re.IGNORECASE)
    matches = list(pattern.finditer(text))
    if not matches:
        return None
    start = matches[-1].end()
    tail = text[start:]
    tail = repair_string_newlines(tail)
    tail_strip = tail.lstrip()

    # Quoted string.
    if tail_strip.startswith('"'):
        escaped = False
        chars = []
        for ch in tail_strip[1:]:
            if escaped:
                chars.append(ch)
                escaped = False
                continue
            if ch == '\\':
                escaped = True
                continue
            if ch == '"':
                return ''.join(chars).strip()
            chars.append(ch)
        return ''.join(chars).strip()

    # Array of strings or simple values.
    if tail_strip.startswith('['):
        depth = 0
        in_string = False
        escaped = False
        for i, ch in enumerate(tail_strip):
            if escaped:
                escaped = False
                continue
            if ch == '\\' and in_string:
                escaped = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    candidate = repair_string_newlines(tail_strip[: i + 1])
                    try:
                        return json.loads(candidate)
                    except Exception:
                        # Fallback: collect quoted fragments.
                        return [m.group(1).strip() for m in re.finditer(r'"([^"\\]*(?:\\.[^"\\]*)*)"', candidate)]
        return []

    # Boolean, null, or number up to comma/brace/newline.
    m = re.match(r'([^,}\n\r]+)', tail_strip)
    if not m:
        return None
    token = m.group(1).strip()
    low = token.lower()
    if low.startswith('true'):
        return True
    if low.startswith('false'):
        return False
    if low.startswith('null'):
        return None
    try:
        if any(c in token for c in ['.', 'e', 'E']):
            return float(re.match(r'[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?', token).group(0))
        return int(re.match(r'[-+]?\d+', token).group(0))
    except Exception:
        return token


def salvage_known_fields(raw: str) -> dict | None:
    """Recover known Task011 fields from badly corrupted JSON-like output."""
    text = strip_terminal_artifacts(raw)
    keys = [
        'status',
        'selected_leptons',
        'electron_count',
        'muon_count',
        'jet_count',
        'b_tagged_jet_count',
        'missing_et_gev',
        'lepton_requirement_passed',
        'jet_requirement_passed',
        'b_tag_requirement_passed',
        'met_requirement_passed',
        'missing_or_failed_requirements',
        'failure_stage',
        'recommended_action',
    ]
    recovered = {}
    for key in keys:
        value = parse_value_by_key(text, key)
        if value is not None:
            recovered[key] = value
    # Require enough fields that this is clearly the requested JSON-like answer.
    required = {'status', 'selected_leptons', 'jet_count', 'b_tagged_jet_count', 'failure_stage'}
    if required.issubset(recovered):
        return recovered
    return None


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

    salvaged = salvage_known_fields(raw)
    if salvaged is not None:
        failures.append("recovered_from_corrupted_json")
        return salvaged, failures

    failures.append("not_parseable_json")
    return None, failures


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
        if lowered in {"true", "yes", "pass", "passed"}:
            return True
        if lowered in {"false", "no", "fail", "failed"}:
            return False
    return None


def normalized_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip().lower() for item in value]
    if isinstance(value, str):
        return [value.strip().lower()]
    return []


def close(value: float | None, expected: float) -> bool:
    return value is not None and abs(value - expected) <= 1e-9


def mentions_btag_failure(items: list[str], recommended_action: str) -> bool:
    text = " ".join(items + [recommended_action.lower()])
    has_b = "b-tag" in text or "btag" in text or "b tagged" in text or "b-jet" in text
    has_two = "2" in text or "two" in text
    has_fail = "fail" in text or "missing" in text or "at least" in text or ">=" in text
    return has_b and (has_two or has_fail)


def score_submission(path: Path) -> dict:
    raw = path.read_text()
    data, failures = extract_json(raw)

    checks = {
        "parseable_json": data is not None,
        "strict_json_only": False,
        "status_invalid": False,
        "selected_leptons_correct": False,
        "electron_count_correct": False,
        "muon_count_correct": False,
        "jet_count_correct": False,
        "b_tagged_jet_count_correct": False,
        "missing_et_correct": False,
        "lepton_requirement_passed": False,
        "jet_requirement_passed": False,
        "b_tag_requirement_failed": False,
        "met_requirement_passed": False,
        "btag_failure_reported": False,
        "failure_stage_object_selection": False,
    }

    normalized = None
    if data is not None:
        checks["strict_json_only"] = not failures

        status = str(data.get("status", "")).strip().lower()
        selected_leptons = as_int(data.get("selected_leptons"))
        electron_count = as_int(data.get("electron_count"))
        muon_count = as_int(data.get("muon_count"))
        jet_count = as_int(data.get("jet_count"))
        b_tagged_jet_count = as_int(data.get("b_tagged_jet_count"))
        missing_et = as_float(data.get("missing_et_gev"))
        lepton_passed = as_bool(data.get("lepton_requirement_passed"))
        jet_passed = as_bool(data.get("jet_requirement_passed"))
        btag_passed = as_bool(data.get("b_tag_requirement_passed"))
        met_passed = as_bool(data.get("met_requirement_passed"))
        failed_requirements = normalized_list(data.get("missing_or_failed_requirements"))
        failure_stage = str(data.get("failure_stage", "")).strip().lower()
        recommended_action = str(data.get("recommended_action", "")).strip().lower()

        checks["status_invalid"] = status == EXPECTED["status"]
        checks["selected_leptons_correct"] = selected_leptons == EXPECTED["selected_leptons"]
        checks["electron_count_correct"] = electron_count == EXPECTED["electron_count"]
        checks["muon_count_correct"] = muon_count == EXPECTED["muon_count"]
        checks["jet_count_correct"] = jet_count == EXPECTED["jet_count"]
        checks["b_tagged_jet_count_correct"] = b_tagged_jet_count == EXPECTED["b_tagged_jet_count"]
        checks["missing_et_correct"] = close(missing_et, EXPECTED["missing_et_gev"])
        checks["lepton_requirement_passed"] = lepton_passed is EXPECTED["lepton_requirement_passed"]
        checks["jet_requirement_passed"] = jet_passed is EXPECTED["jet_requirement_passed"]
        checks["b_tag_requirement_failed"] = btag_passed is EXPECTED["b_tag_requirement_passed"]
        checks["met_requirement_passed"] = met_passed is EXPECTED["met_requirement_passed"]
        checks["btag_failure_reported"] = mentions_btag_failure(failed_requirements, recommended_action)
        checks["failure_stage_object_selection"] = failure_stage == EXPECTED["failure_stage"]

        normalized = {
            "status": status,
            "selected_leptons": selected_leptons,
            "electron_count": electron_count,
            "muon_count": muon_count,
            "jet_count": jet_count,
            "b_tagged_jet_count": b_tagged_jet_count,
            "missing_et_gev": missing_et,
            "lepton_requirement_passed": lepton_passed,
            "jet_requirement_passed": jet_passed,
            "b_tag_requirement_passed": btag_passed,
            "met_requirement_passed": met_passed,
            "missing_or_failed_requirements": failed_requirements,
            "failure_stage": failure_stage,
            "recommended_action": recommended_action,
        }

        failure_map = {
            "status_invalid": "wrong_status",
            "selected_leptons_correct": "wrong_selected_leptons",
            "electron_count_correct": "wrong_electron_count",
            "muon_count_correct": "wrong_muon_count",
            "jet_count_correct": "wrong_jet_count",
            "b_tagged_jet_count_correct": "wrong_b_tagged_jet_count",
            "missing_et_correct": "wrong_missing_et",
            "lepton_requirement_passed": "wrong_lepton_requirement",
            "jet_requirement_passed": "wrong_jet_requirement",
            "b_tag_requirement_failed": "missed_b_tag_failure",
            "met_requirement_passed": "wrong_met_requirement",
            "btag_failure_reported": "missing_b_tag_failure_report",
            "failure_stage_object_selection": "wrong_failure_stage",
        }
        for check, failure in failure_map.items():
            if not checks[check]:
                failures.append(failure)

    weights = {
        "parseable_json": 0.10,
        "strict_json_only": 0.03,
        "status_invalid": 0.07,
        "selected_leptons_correct": 0.07,
        "electron_count_correct": 0.05,
        "muon_count_correct": 0.05,
        "jet_count_correct": 0.07,
        "b_tagged_jet_count_correct": 0.09,
        "missing_et_correct": 0.06,
        "lepton_requirement_passed": 0.06,
        "jet_requirement_passed": 0.06,
        "b_tag_requirement_failed": 0.11,
        "met_requirement_passed": 0.06,
        "btag_failure_reported": 0.08,
        "failure_stage_object_selection": 0.04,
    }
    score = sum(weight for key, weight in weights.items() if checks[key])

    passed = (
        checks["parseable_json"]
        and checks["status_invalid"]
        and checks["selected_leptons_correct"]
        and checks["electron_count_correct"]
        and checks["muon_count_correct"]
        and checks["jet_count_correct"]
        and checks["b_tagged_jet_count_correct"]
        and checks["missing_et_correct"]
        and checks["lepton_requirement_passed"]
        and checks["jet_requirement_passed"]
        and checks["b_tag_requirement_failed"]
        and checks["met_requirement_passed"]
        and checks["btag_failure_reported"]
        and checks["failure_stage_object_selection"]
    )
    strict_passed = passed and checks["strict_json_only"]

    return {
        "task_id": "delphes_objects_011",
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
