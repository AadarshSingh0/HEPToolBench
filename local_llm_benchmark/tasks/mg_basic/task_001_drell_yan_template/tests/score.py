#!/usr/bin/env python3
"""Score mg_basic_001 submissions.

This lightweight scorer does static checks only. A later version can add
optional MadGraph execution when MG5 is available in the environment.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def normalize(text: str) -> str:
    lines = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(re.sub(r"\s+", " ", stripped))
    return "\n".join(lines)


def has_line(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE) is not None


def parse_beam_energy(name: str, text: str) -> float | None:
    match = re.search(rf"^\s*(?:set\s+)?{name}\s*(?:=)?\s*([0-9.eE+-]+)", text, re.IGNORECASE | re.MULTILINE)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def score_submission(path: Path) -> dict:
    raw = path.read_text()
    text = normalize(raw)

    checks = {}
    failures = []

    checks["imports_sm"] = has_line(r"^import model sm$", text)
    checks["defines_proton"] = has_line(r"^define p = .*", text)
    checks["correct_process"] = has_line(r"^generate p p > e\+ e-$", text)
    checks["has_output"] = has_line(r"^output\s+\S+", text)
    checks["has_launch"] = has_line(r"^launch$", text)
    checks["no_markdown_fence"] = "```" not in raw
    checks["no_reasoning_tags"] = not re.search(r"</?think>|<\|im_start\|>|<\|endoftext\|>", raw, re.IGNORECASE)
    checks["no_prompt_echo"] = "TASK INSTRUCTION:" not in raw and "MADGRAPH TEMPLATE:" not in raw
    checks["no_interactive_prompt"] = not has_line(r"^MadGraph5\s*:", text)
    checks["no_long_explanation"] = not re.search(
        r"standard MadGraph|following steps|Process Definition|Beam Energy|Completed `?proc_card",
        raw,
        re.IGNORECASE,
    )

    ebeam1 = parse_beam_energy("ebeam1", text)
    ebeam2 = parse_beam_energy("ebeam2", text)
    checks["ebeam1_6500"] = ebeam1 == 6500.0
    checks["ebeam2_6500"] = ebeam2 == 6500.0

    if has_line(r"^generate pp", text):
        failures.append("invalid_initial_state_pp_compact")
    if has_line(r"->", text):
        failures.append("uses_arrow_instead_of_madgraph_gt")
    if has_line(r"^process\s*=", text):
        failures.append("uses_non_madgraph_process_assignment")
    if has_line(r"^process$", text):
        failures.append("uses_standalone_process_keyword")
    if has_line(r"^p p > e\+ e-$", text):
        failures.append("missing_generate_keyword")
    if has_line(r";", text):
        failures.append("uses_semicolon_syntax")
    if has_line(r"^set\s+beamenergies\b", text):
        failures.append("uses_invalid_beamenergies_command")
    if has_line(r"^set\s+beam1\b", text) or has_line(r"^set\s+beam2\b", text):
        failures.append("uses_invalid_beam1_beam2_commands")
    if has_line(r"^launch,", text):
        failures.append("punctuation_after_launch")
    if not checks["no_markdown_fence"]:
        failures.append("includes_markdown_fence")
    if not checks["no_reasoning_tags"]:
        failures.append("includes_reasoning_or_chat_tags")
    if not checks["no_prompt_echo"]:
        failures.append("echoes_prompt")
    if not checks["no_interactive_prompt"]:
        failures.append("uses_interactive_madgraph_prompt")
    if not checks["no_long_explanation"]:
        failures.append("includes_explanation_not_file_only")
    if has_line(r"^generate p p > e e$", text):
        failures.append("missing_electron_charges")
    if ebeam1 == 13000.0 or ebeam2 == 13000.0:
        failures.append("uses_total_energy_as_each_beam")
    if not checks["correct_process"]:
        failures.append("missing_or_wrong_process")
    if not checks["ebeam1_6500"] or not checks["ebeam2_6500"]:
        failures.append("wrong_or_missing_beam_energy")

    weights = {
        "imports_sm": 0.10,
        "defines_proton": 0.10,
        "correct_process": 0.30,
        "has_output": 0.075,
        "has_launch": 0.05,
        "no_markdown_fence": 0.025,
        "no_reasoning_tags": 0.025,
        "no_prompt_echo": 0.025,
        "no_interactive_prompt": 0.025,
        "no_long_explanation": 0.025,
        "ebeam1_6500": 0.125,
        "ebeam2_6500": 0.125,
    }
    score = sum(weight for key, weight in weights.items() if checks[key])
    formatting_failures = {
        "includes_markdown_fence",
        "includes_explanation_not_file_only",
        "includes_reasoning_or_chat_tags",
        "echoes_prompt",
    }
    core_failures = {
        "missing_or_wrong_process",
        "wrong_or_missing_beam_energy",
        "uses_interactive_madgraph_prompt",
    }

    failure_set = set(failures)
    if formatting_failures.intersection(failure_set):
        score = min(score, 0.50)
    if core_failures.intersection(failure_set):
        score = min(score, 0.60)
    if formatting_failures.intersection(failure_set) and core_failures.intersection(failure_set):
        score = min(score, 0.45)

    hard_failures = {
        "includes_markdown_fence",
        "invalid_initial_state_pp_compact",
        "uses_arrow_instead_of_madgraph_gt",
        "uses_invalid_beamenergies_command",
        "uses_invalid_beam1_beam2_commands",
        "uses_non_madgraph_process_assignment",
        "uses_standalone_process_keyword",
        "missing_generate_keyword",
        "punctuation_after_launch",
        "uses_semicolon_syntax",
        "includes_explanation_not_file_only",
        "includes_reasoning_or_chat_tags",
        "echoes_prompt",
        "uses_interactive_madgraph_prompt",
    }
    passed = (
        checks["correct_process"]
        and checks["ebeam1_6500"]
        and checks["ebeam2_6500"]
        and not hard_failures.intersection(failures)
    )

    return {
        "task_id": "mg_basic_001",
        "score": round(score, 3),
        "passed": passed,
        "checks": checks,
        "failure_modes": sorted(set(failures)),
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
