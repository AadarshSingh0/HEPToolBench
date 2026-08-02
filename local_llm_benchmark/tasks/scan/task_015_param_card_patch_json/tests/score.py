#!/usr/bin/env python3
"""Score Task015: param_card.dat patch plan for one scan point."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def strip_terminal_artifacts(text: str) -> tuple[str, bool]:
    original = text
    text = ANSI_RE.sub("", text)
    text = text.replace("\r", "")
    # Remove common chat sentinels seen in reasoning models.
    text = re.sub(r"<\|[^>]+\|>", "", text)
    text = text.replace("</think>", "")
    return text, text != original


def remove_markdown_fences(text: str) -> tuple[str, bool]:
    had = "```" in text
    # Prefer content inside a fenced block if present.
    blocks = re.findall(r"```(?:json|text)?\s*(.*?)```", text, flags=re.I | re.S)
    if blocks:
        return "\n".join(blocks).strip(), True
    return text, had


def _escape_newlines_inside_strings(s: str) -> str:
    out = []
    in_str = False
    esc = False
    for ch in s:
        if in_str:
            if esc:
                out.append(ch)
                esc = False
            elif ch == "\\":
                out.append(ch)
                esc = True
            elif ch == '"':
                out.append(ch)
                in_str = False
            elif ch in "\n\t":
                out.append(" ")
            else:
                out.append(ch)
        else:
            out.append(ch)
            if ch == '"':
                in_str = True
    return "".join(out)


def json_candidates(text: str) -> list[str]:
    candidates = []
    stack = []
    start = None
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if not stack:
                start = i
            stack.append(ch)
        elif ch == "}" and stack:
            stack.pop()
            if not stack and start is not None:
                candidates.append(text[start : i + 1])
                start = None
    # longest/fullest objects first; reasoning often contains tiny example objects before the final answer
    return sorted(set(candidates + [text.strip()]), key=len, reverse=True)


def parse_json_robust(raw: str) -> tuple[Any | None, dict[str, bool]]:
    flags = {
        "terminal_artifacts_removed": False,
        "includes_markdown_fence": False,
        "includes_explanation_not_json_only": False,
        "strict_json_only": False,
    }
    stripped = raw.strip()
    obj = None
    try:
        obj = json.loads(stripped)
        flags["strict_json_only"] = isinstance(obj, dict)
        return obj, flags
    except Exception:
        pass

    cleaned, changed = strip_terminal_artifacts(raw)
    flags["terminal_artifacts_removed"] = changed
    unfenced, had_fence = remove_markdown_fences(cleaned)
    flags["includes_markdown_fence"] = had_fence
    flags["includes_explanation_not_json_only"] = cleaned.strip() != unfenced.strip() or not cleaned.strip().startswith("{") or not cleaned.strip().endswith("}")

    for cand in json_candidates(unfenced):
        for attempt in (cand, _escape_newlines_inside_strings(cand)):
            try:
                parsed = json.loads(attempt)
                if isinstance(parsed, dict):
                    return parsed, flags
            except Exception:
                continue
    return None, flags


def norm_str(x: Any) -> str:
    return str(x).strip().lower().replace("_", " ").replace("-", " ")


def compact(x: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(x).lower())


def as_float(x: Any) -> float | None:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    m = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", str(x))
    return float(m.group(0)) if m else None


def close(x: Any, target: float, rel: float = 1e-6, abs_tol: float = 1e-6) -> bool:
    val = as_float(x)
    return val is not None and math.isclose(val, target, rel_tol=rel, abs_tol=abs_tol)


def flatten_updates(obj: dict[str, Any]) -> list[dict[str, Any]]:
    keys = ["updates", "patches", "parameters_to_update", "changes", "edits"]
    out: list[dict[str, Any]] = []
    for key in keys:
        value = obj.get(key)
        if isinstance(value, list):
            out.extend([x for x in value if isinstance(x, dict)])
        elif isinstance(value, dict):
            out.extend([value])
    # Some models use a nested patch object.
    patch = obj.get("patch") or obj.get("param_card_patch")
    if isinstance(patch, dict):
        for key in keys:
            value = patch.get(key)
            if isinstance(value, list):
                out.extend([x for x in value if isinstance(x, dict)])
            elif isinstance(value, dict):
                out.extend([value])
    return out


def unchanged_entries(obj: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key in ("unchanged", "unchanged_parameters", "do_not_modify", "kept_fixed"):
        value = obj.get(key)
        if isinstance(value, list):
            out.extend([x for x in value if isinstance(x, dict)])
        elif isinstance(value, dict):
            out.append(value)
    return out


def field_text(d: dict[str, Any], keys: list[str]) -> str:
    return " ".join(str(d.get(k, "")) for k in keys)


def is_mass_update(d: dict[str, Any]) -> bool:
    text = compact(field_text(d, ["block", "parameter", "name", "identifier", "pdg", "pdg_code", "comment"]))
    return ("mass" in text or "ms" in text) and ("9000001" in text or "ms" in text)


def is_coupling_update(d: dict[str, Any]) -> bool:
    text = compact(field_text(d, ["block", "parameter", "name", "identifier", "index", "comment"]))
    return ("couplings" in text or "coupling" in text or "gs" in text) and ("1" in text or "gs" in text)


def get_new_value(d: dict[str, Any]) -> Any:
    for key in ("new_value", "new", "value", "set_to", "target_value"):
        if key in d:
            return d[key]
    return None


def get_old_value(d: dict[str, Any]) -> Any:
    for key in ("old_value", "old", "current_value", "from"):
        if key in d:
            return d[key]
    return None


def block_is(d: dict[str, Any], name: str) -> bool:
    return name.lower() in norm_str(d.get("block", ""))


def identifier_has(d: dict[str, Any], ident: str) -> bool:
    return ident in str(d.get("identifier", "")) or ident in str(d.get("pdg", "")) or ident in str(d.get("pdg_code", "")) or ident in str(d.get("index", ""))


def score_plan(obj: dict[str, Any], flags: dict[str, bool]) -> dict[str, Any]:
    updates = flatten_updates(obj)
    unchanged = unchanged_entries(obj)
    mass = next((u for u in updates if is_mass_update(u)), None)
    coup = next((u for u in updates if is_coupling_update(u)), None)

    # Detect bad width modifications.
    width_updates = []
    for u in updates:
        text = compact(field_text(u, ["block", "parameter", "name", "identifier", "comment"]))
        if "decay" in text or "width" in text or "9000001" in text and close(get_new_value(u), 0.001):
            # do not count the mass update just because it has 9000001
            if not is_mass_update(u):
                width_updates.append(u)
    decay_not_modified = len(width_updates) == 0
    decay_ack = decay_not_modified or any("decay" in compact(field_text(u, ["block", "parameter", "name", "reason"])) or "width" in compact(field_text(u, ["block", "parameter", "name", "reason"])) for u in unchanged)

    file_text = compact(obj.get("file_to_modify") or obj.get("file") or obj.get("target_file") or "")
    status_text = compact(obj.get("status", ""))
    label_text = compact(obj.get("scan_point_label") or obj.get("label") or obj.get("point_label") or "")

    checks = {
        "parseable_json": True,
        "strict_json_only": flags.get("strict_json_only", False),
        "status_valid": status_text in {"valid", "ready", "ok"},
        "file_to_modify_param_card": "paramcard" in file_text or "modelparametercard" in file_text,
        "mass_update_present": mass is not None,
        "mass_block_correct": mass is not None and block_is(mass, "MASS"),
        "mass_identifier_correct": mass is not None and identifier_has(mass, "9000001"),
        "mass_old_value_correct": mass is not None and close(get_old_value(mass), 1.0),
        "mass_new_value_correct": mass is not None and close(get_new_value(mass), 3.5),
        "mass_unit_correct": mass is not None and ("gev" in norm_str(mass.get("unit", "GeV")) or mass.get("unit") in (None, "")),
        "coupling_update_present": coup is not None,
        "coupling_block_correct": coup is not None and (block_is(coup, "COUPLINGS") or "coupling" in norm_str(coup.get("block", ""))),
        "coupling_identifier_correct": coup is not None and (identifier_has(coup, "1") or "gs" in compact(field_text(coup, ["parameter", "name", "comment"]))),
        "coupling_old_value_correct": coup is not None and close(get_old_value(coup), 0.05),
        "coupling_new_value_correct": coup is not None and close(get_new_value(coup), 0.1),
        "decay_width_not_modified": decay_not_modified,
        "decay_width_unchanged_acknowledged": decay_ack,
        "scan_point_label_correct": "3p5" in label_text and "0p1" in label_text,
    }

    weights = {
        "status_valid": 0.06,
        "file_to_modify_param_card": 0.08,
        "mass_update_present": 0.08,
        "mass_block_correct": 0.08,
        "mass_identifier_correct": 0.08,
        "mass_old_value_correct": 0.06,
        "mass_new_value_correct": 0.12,
        "mass_unit_correct": 0.03,
        "coupling_update_present": 0.08,
        "coupling_block_correct": 0.06,
        "coupling_identifier_correct": 0.06,
        "coupling_old_value_correct": 0.05,
        "coupling_new_value_correct": 0.10,
        "decay_width_not_modified": 0.04,
        "decay_width_unchanged_acknowledged": 0.01,
        "scan_point_label_correct": 0.01,
    }
    assert abs(sum(weights.values()) - 1.0) < 1e-12
    score = sum(w for k, w in weights.items() if checks.get(k, False))

    failure_modes = []
    if flags.get("includes_markdown_fence"):
        failure_modes.append("includes_markdown_fence")
    if flags.get("includes_explanation_not_json_only"):
        failure_modes.append("includes_explanation_not_json_only")
    if flags.get("terminal_artifacts_removed"):
        failure_modes.append("terminal_artifacts_removed")
    if not checks["status_valid"]:
        failure_modes.append("status_not_valid")
    if not checks["file_to_modify_param_card"]:
        failure_modes.append("wrong_or_missing_target_file")
    if not checks["mass_update_present"]:
        failure_modes.append("missing_mass_update")
    if not checks["mass_new_value_correct"]:
        failure_modes.append("wrong_mass_value")
    if not checks["coupling_update_present"]:
        failure_modes.append("missing_coupling_update")
    if not checks["coupling_new_value_correct"]:
        failure_modes.append("wrong_coupling_value")
    if not checks["decay_width_not_modified"]:
        failure_modes.append("incorrectly_modifies_decay_width")

    core = [
        "parseable_json",
        "status_valid",
        "file_to_modify_param_card",
        "mass_update_present",
        "mass_block_correct",
        "mass_identifier_correct",
        "mass_new_value_correct",
        "coupling_update_present",
        "coupling_new_value_correct",
        "decay_width_not_modified",
    ]
    passed = all(checks.get(k, False) for k in core)

    # Penalize non-strict output slightly but do not turn a semantically correct patch into a failure.
    if not checks["strict_json_only"] and score > 0:
        score = max(0.0, score - 0.03)

    normalized = {
        "status": obj.get("status"),
        "file_to_modify": obj.get("file_to_modify") or obj.get("file") or obj.get("target_file"),
        "mass_new_value": as_float(get_new_value(mass)) if mass else None,
        "coupling_new_value": as_float(get_new_value(coup)) if coup else None,
        "decay_width_not_modified": decay_not_modified,
        "scan_point_label": obj.get("scan_point_label") or obj.get("label") or obj.get("point_label"),
    }

    return {
        "checks": checks,
        "failure_modes": failure_modes,
        "normalized_patch": normalized,
        "passed": passed,
        "score": round(score, 3),
        "strict_passed": passed and checks["strict_json_only"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    raw = args.submission.read_text(errors="replace")
    parsed, flags = parse_json_robust(raw)
    if not isinstance(parsed, dict):
        result = {
            "task_id": "param_card_patch_015",
            "submission": str(args.submission),
            "checks": {"parseable_json": False, "strict_json_only": False},
            "failure_modes": ["not_parseable_json"],
            "normalized_patch": None,
            "passed": False,
            "score": 0,
            "strict_passed": False,
        }
    else:
        result = score_plan(parsed, flags)
        result.update({"task_id": "param_card_patch_015", "submission": str(args.submission)})

    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
