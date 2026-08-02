#!/usr/bin/env python3
"""Score cutflow_diagnosis_013 submissions."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ANSI_RE = re.compile("\x1b\\[[0-?]*[ -/]*[@-~]")

EXPECTED = {
    "status": "low_statistics",
    "final_signal_events": 48,
    "final_background_events": 120,
    "dominant_signal_loss_cut": "transverse-mass window",
    "dominant_signal_loss_step_efficiency": 0.0923,
    "dominant_signal_loss_fraction": 0.9077,
    "s_over_sqrt_b": 4.38,
    "statistically_usable": False,
}


def strip_terminal_artifacts(raw: str) -> str:
    """Remove ANSI/cursor-control artifacts and simulate backspace deletion."""
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
    candidates: list[str] = []
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
        chars: list[str] = []
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
    chunk_match = re.match(r'([^,}]+)', tail, flags=re.DOTALL)
    if not chunk_match:
        return None
    chunk = chunk_match.group(1).strip()
    compact = re.sub(r"\s+", "", chunk).lower()
    if "true" in compact and "false" not in compact:
        return True
    if "false" in compact and "true" not in compact:
        return False
    if compact.startswith("null"):
        return None
    nums = re.findall(r'[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?', chunk)
    if nums:
        s = nums[-1]
        return float(s) if any(c in s for c in ".eE") else int(s)
    return chunk.strip()


def salvage_known_fields(raw: str) -> dict | None:
    text = strip_terminal_artifacts(raw)
    keys = [
        "status",
        "final_signal_events",
        "final_background_events",
        "dominant_signal_loss_cut",
        "dominant_signal_loss_step_efficiency",
        "dominant_signal_loss_fraction",
        "s_over_sqrt_b",
        "statistically_usable",
        "recommended_action",
    ]
    recovered = {}
    for key in keys:
        value = parse_value_by_key(text, key)
        if value is not None:
            recovered[key] = value
    required = {"status", "final_signal_events", "final_background_events", "dominant_signal_loss_cut", "statistically_usable"}
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
        if lowered in {"true", "yes", "usable", "pass", "passed"}:
            return True
        if lowered in {"false", "no", "not usable", "low_statistics", "low statistics", "fail", "failed"}:
            return False
    return None


def close(value: float | None, expected: float, tol: float) -> bool:
    return value is not None and abs(value - expected) <= tol


def norm_text(value) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def cut_is_transverse_mass(value) -> bool:
    text = norm_text(value)
    return (
        "transverse" in text and "mass" in text
    ) or text in {"mt window", "m t window", "mass window", "transverse mass window"}


def status_low_statistics(value) -> bool:
    text = norm_text(value)
    return any(token in text for token in ["low statistics", "low statistic", "insufficient", "not usable", "invalid"])


def recommendation_mentions_statistics(action: str) -> bool:
    text = norm_text(action)
    return any(word in text for word in ["statistics", "statistic", "events", "increase", "loosen", "simulate", "transverse", "mass"])


def score_submission(path: Path) -> dict:
    raw = path.read_text(errors="replace")
    data, failures = extract_json(raw)

    checks = {
        "parseable_json": data is not None,
        "strict_json_only": False,
        "status_low_statistics": False,
        "final_signal_correct": False,
        "final_background_correct": False,
        "dominant_loss_cut_correct": False,
        "step_efficiency_correct": False,
        "loss_fraction_correct": False,
        "s_over_sqrt_b_correct": False,
        "statistically_unusable": False,
        "recommended_action_mentions_statistics": False,
    }

    normalized = None
    if data is not None:
        checks["strict_json_only"] = not failures
        status = str(data.get("status", "")).strip().lower()
        final_signal = as_int(data.get("final_signal_events"))
        final_background = as_int(data.get("final_background_events"))
        dominant_cut = str(data.get("dominant_signal_loss_cut", "")).strip()
        step_eff = as_float(data.get("dominant_signal_loss_step_efficiency"))
        loss_frac = as_float(data.get("dominant_signal_loss_fraction"))
        significance = as_float(data.get("s_over_sqrt_b"))
        usable = as_bool(data.get("statistically_usable"))
        action = str(data.get("recommended_action", "")).strip()

        checks["status_low_statistics"] = status_low_statistics(status)
        checks["final_signal_correct"] = final_signal == EXPECTED["final_signal_events"]
        checks["final_background_correct"] = final_background == EXPECTED["final_background_events"]
        checks["dominant_loss_cut_correct"] = cut_is_transverse_mass(dominant_cut)
        checks["step_efficiency_correct"] = close(step_eff, EXPECTED["dominant_signal_loss_step_efficiency"], tol=5e-4)
        checks["loss_fraction_correct"] = close(loss_frac, EXPECTED["dominant_signal_loss_fraction"], tol=5e-4)
        checks["s_over_sqrt_b_correct"] = close(significance, EXPECTED["s_over_sqrt_b"], tol=0.02)
        checks["statistically_unusable"] = usable is False
        checks["recommended_action_mentions_statistics"] = recommendation_mentions_statistics(action)

        normalized = {
            "status": status,
            "final_signal_events": final_signal,
            "final_background_events": final_background,
            "dominant_signal_loss_cut": dominant_cut,
            "dominant_signal_loss_step_efficiency": step_eff,
            "dominant_signal_loss_fraction": loss_frac,
            "s_over_sqrt_b": significance,
            "statistically_usable": usable,
            "recommended_action": action,
        }

        failure_map = {
            "status_low_statistics": "wrong_status",
            "final_signal_correct": "wrong_final_signal_events",
            "final_background_correct": "wrong_final_background_events",
            "dominant_loss_cut_correct": "wrong_dominant_signal_loss_cut",
            "step_efficiency_correct": "wrong_step_efficiency",
            "loss_fraction_correct": "wrong_loss_fraction",
            "s_over_sqrt_b_correct": "wrong_s_over_sqrt_b",
            "statistically_unusable": "wrong_statistical_usability",
            "recommended_action_mentions_statistics": "weak_recommended_action",
        }
        for check, failure in failure_map.items():
            if not checks[check]:
                failures.append(failure)

    weights = {
        "parseable_json": 0.08,
        "strict_json_only": 0.03,
        "status_low_statistics": 0.08,
        "final_signal_correct": 0.10,
        "final_background_correct": 0.08,
        "dominant_loss_cut_correct": 0.16,
        "step_efficiency_correct": 0.12,
        "loss_fraction_correct": 0.12,
        "s_over_sqrt_b_correct": 0.09,
        "statistically_unusable": 0.09,
        "recommended_action_mentions_statistics": 0.05,
    }
    assert abs(sum(weights.values()) - 1.0) < 1e-12
    score = sum(weight for key, weight in weights.items() if checks[key])

    required_for_pass = [
        "parseable_json",
        "status_low_statistics",
        "final_signal_correct",
        "final_background_correct",
        "dominant_loss_cut_correct",
        "step_efficiency_correct",
        "loss_fraction_correct",
        "s_over_sqrt_b_correct",
        "statistically_unusable",
        "recommended_action_mentions_statistics",
    ]
    passed = all(checks[key] for key in required_for_pass)
    strict_passed = passed and checks["strict_json_only"]

    return {
        "task_id": "cutflow_diagnosis_013",
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
