#!/usr/bin/env python3
"""Score mg_debug_structured_001 structured repair-patch submissions."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TASK_ID = "mg_debug_structured_001"
FAULTY_HINTS = ['p p > e+ e-', 'beam1', 'beam2']
REQUIRED_CORRECTED_LINES = ['generate p p > e+ e-', 'set ebeam1 6500', 'set ebeam2 6500', 'output DY_ee']
CORRECT_PROCESS = "generate p p > e+ e-"
OUTPUT_DIR = "DY_ee"
FORBIDDEN_PATTERNS = ['process', '->', 'beam1', 'beam2', 'tbar', 'jet']


def norm(text: str) -> str:
    text = str(text).lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def flatten(value) -> str:
    if isinstance(value, list):
        return "\n".join(str(x) for x in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value or "")


def extract_json(raw: str):
    failures = []
    text = raw.strip()
    try:
        return json.loads(text), failures
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json|text)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        failures.append("includes_markdown_fence")
        try:
            return json.loads(fence.group(1)), failures
        except json.JSONDecodeError:
            failures.append("invalid_json_inside_markdown")

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        failures.append("includes_explanation_not_json_only")
        try:
            return json.loads(raw[start:end + 1]), failures
        except json.JSONDecodeError:
            failures.append("invalid_json_substring")

    failures.append("not_parseable_json")
    return None, failures


def contains_any(text: str, needles: list[str]) -> bool:
    low = norm(text)
    return any(norm(n) in low for n in needles)


def corrected_line_hits(text: str) -> int:
    low = norm(text)
    return sum(1 for line in REQUIRED_CORRECTED_LINES if norm(line) in low)


def has_forbidden_syntax(text: str) -> bool:
    """
    Detect invalid MadGraph repair syntax.

    This must NOT flag valid MadGraph commands such as:
        set ebeam1 6500
        set ebeam2 6500

    It only flags standalone invalid tokens/commands:
        beam1
        beam2
        process
        ->
    plus task-specific invalid aliases.
    """
    for raw_line in str(text).splitlines():
        line = norm(raw_line)
        if not line:
            continue

        # Wrong arrow notation instead of MadGraph ">"
        if "->" in line:
            return True

        # Wrong command keyword
        if re.search(r"(^|\s)process(\s|$)", line):
            return True

        # Invalid standalone beam commands.
        # Do not match valid "ebeam1" or "ebeam2".
        if re.search(r"(^|\s)beam1(\s|$)", line):
            return True
        if re.search(r"(^|\s)beam2(\s|$)", line):
            return True

        # Task-specific invalid aliases
        if TASK_ID == "mg_debug_structured_002":
            if re.search(r"(^|\s)tbar(\s|$)", line):
                return True

        if TASK_ID == "mg_debug_structured_003":
            if re.search(r"(^|\s)jet(\s|$)", line):
                return True
            if "higgsjet" in line:
                return True

    return False

def score_submission(path: Path) -> dict:
    raw = path.read_text(errors="ignore")
    data, failures = extract_json(raw)

    checks = {
        "parseable_json": data is not None,
        "strict_json_only": data is not None and not failures,
        "has_error_type": False,
        "has_faulty_lines": False,
        "faulty_lines_identify_problem": False,
        "has_corrected_lines": False,
        "correct_process_present": False,
        "required_corrected_line_hits": 0,
        "beam_energy_fixed": False,
        "output_dir_correct": False,
        "has_reason": False,
        "no_forbidden_syntax_in_corrections": False,
    }

    corrected_text = ""
    faulty_text = ""

    if data is not None:
        checks["has_error_type"] = bool(str(data.get("error_type", "")).strip())
        checks["has_reason"] = bool(str(data.get("reason", "")).strip())

        faulty_text = flatten(data.get("faulty_lines"))
        corrected_text = flatten(data.get("corrected_lines"))
        output_dir = str(data.get("output_dir", "")).strip()

        checks["has_faulty_lines"] = bool(faulty_text.strip())
        checks["faulty_lines_identify_problem"] = contains_any(faulty_text, FAULTY_HINTS)
        checks["has_corrected_lines"] = bool(corrected_text.strip())
        checks["correct_process_present"] = norm(CORRECT_PROCESS) in norm(corrected_text)
        checks["required_corrected_line_hits"] = corrected_line_hits(corrected_text)
        checks["beam_energy_fixed"] = ("set ebeam1 6500" in norm(corrected_text)) and ("set ebeam2 6500" in norm(corrected_text))
        checks["output_dir_correct"] = norm(output_dir) == norm(OUTPUT_DIR) or (norm("output " + OUTPUT_DIR) in norm(corrected_text))
        checks["no_forbidden_syntax_in_corrections"] = not has_forbidden_syntax(corrected_text)

        if not checks["has_error_type"]:
            failures.append("missing_error_type")
        if not checks["has_faulty_lines"]:
            failures.append("missing_faulty_lines")
        elif not checks["faulty_lines_identify_problem"]:
            failures.append("faulty_lines_do_not_identify_problem")
        if not checks["has_corrected_lines"]:
            failures.append("missing_corrected_lines")
        if not checks["correct_process_present"]:
            failures.append("missing_or_wrong_correct_process")
        if not checks["beam_energy_fixed"]:
            failures.append("missing_or_wrong_ebeam_repairs")
        if not checks["output_dir_correct"]:
            failures.append("missing_or_wrong_output_dir")
        if not checks["has_reason"]:
            failures.append("missing_reason")
        if not checks["no_forbidden_syntax_in_corrections"]:
            failures.append("forbidden_syntax_in_corrected_lines")

    score = 0.0
    score += 0.10 if checks["parseable_json"] else 0.0
    score += 0.05 if checks["strict_json_only"] else 0.0
    score += 0.07 if checks["has_error_type"] else 0.0
    score += 0.06 if checks["has_faulty_lines"] else 0.0
    score += 0.10 if checks["faulty_lines_identify_problem"] else 0.0
    score += 0.07 if checks["has_corrected_lines"] else 0.0
    score += 0.25 if checks["correct_process_present"] else 0.0
    if REQUIRED_CORRECTED_LINES:
        score += 0.15 * checks["required_corrected_line_hits"] / len(REQUIRED_CORRECTED_LINES)
    score += 0.10 if checks["beam_energy_fixed"] else 0.0
    score += 0.05 if checks["output_dir_correct"] else 0.0
    score += 0.05 if checks["has_reason"] else 0.0
    score += 0.05 if checks["no_forbidden_syntax_in_corrections"] else 0.0

    passed = (
        checks["parseable_json"]
        and checks["correct_process_present"]
        and checks["beam_energy_fixed"]
        and checks["output_dir_correct"]
        and checks["no_forbidden_syntax_in_corrections"]
        and score >= 0.75
    )

    return {
        "task_id": TASK_ID,
        "score": round(min(score, 1.0), 3),
        "passed": bool(passed),
        "checks": checks,
        "failure_modes": sorted(set(failures)),
        "submission": str(path),
        "faulty_lines_text": faulty_text,
        "corrected_lines_text": corrected_text,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = score_submission(args.submission)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
