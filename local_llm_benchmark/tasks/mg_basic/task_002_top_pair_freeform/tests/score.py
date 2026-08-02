#!/usr/bin/env python3
"""Score mg_basic_002 submissions."""

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
    failures = []

    checks = {
        "imports_sm": has_line(r"^import model sm$", text),
        "defines_proton": has_line(r"^define p = .*", text),
        "correct_proton_definition": has_line(r"^define p = g u c d s u~ c~ d~ s~$", text),
        "correct_process": has_line(r"^generate p p > t t~$", text),
        "has_output_ttbar": has_line(r"^output TTbar$", text),
        "has_launch": has_line(r"^launch$", text),
        "no_markdown_fence": "```" not in raw,
        "no_reasoning_tags": not re.search(r"</?think>|<\|im_start\|>|<\|endoftext\|>", raw, re.IGNORECASE),
        "no_prompt_echo": "TASK INSTRUCTION:" not in raw and "MADGRAPH TEMPLATE:" not in raw,
        "no_long_explanation": not re.search(
            r"standard MadGraph|following steps|Process Definition|Beam Energy|Completed `?proc_card|top-pair production",
            raw,
            re.IGNORECASE,
        ),
    }

    ebeam1 = parse_beam_energy("ebeam1", text)
    ebeam2 = parse_beam_energy("ebeam2", text)
    checks["ebeam1_6500"] = ebeam1 == 6500.0
    checks["ebeam2_6500"] = ebeam2 == 6500.0

    if checks["defines_proton"] and not checks["correct_proton_definition"]:
        failures.append("wrong_proton_definition")
    if has_line(r"^p p > t t~$", text):
        failures.append("missing_generate_keyword")
    if has_line(r"^generate p p > t tbar$", text) or has_line(r"^p p > t tbar$", text):
        failures.append("uses_tbar_instead_of_t_tilde")
    if has_line(r"^generate p p > t anti", text):
        failures.append("uses_words_instead_of_madgraph_antiparticle")
    if has_line(r"->", text):
        failures.append("uses_arrow_instead_of_madgraph_gt")
    if has_line(r"^process\b", text):
        failures.append("uses_process_keyword")
    if has_line(r"^set\s+beam1\b", text) or has_line(r"^set\s+beam2\b", text):
        failures.append("uses_invalid_beam1_beam2_commands")
    if has_line(r"^set\s+beamenergies\b", text):
        failures.append("uses_invalid_beamenergies_command")
    if ebeam1 == 13000.0 or ebeam2 == 13000.0:
        failures.append("uses_total_energy_as_each_beam")
    if not checks["no_markdown_fence"]:
        failures.append("includes_markdown_fence")
    if not checks["no_reasoning_tags"]:
        failures.append("includes_reasoning_or_chat_tags")
    if not checks["no_prompt_echo"]:
        failures.append("echoes_prompt")
    if not checks["no_long_explanation"]:
        failures.append("includes_explanation_not_file_only")
    if not checks["correct_process"]:
        failures.append("missing_or_wrong_process")
    if not checks["has_output_ttbar"]:
        failures.append("missing_or_wrong_output")
    if not checks["ebeam1_6500"] or not checks["ebeam2_6500"]:
        failures.append("wrong_or_missing_beam_energy")

    weights = {
        "imports_sm": 0.10,
        "defines_proton": 0.10,
        "correct_proton_definition": 0.025,
        "correct_process": 0.30,
        "has_output_ttbar": 0.075,
        "has_launch": 0.05,
        "no_markdown_fence": 0.025,
        "no_reasoning_tags": 0.025,
        "no_prompt_echo": 0.025,
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
        "missing_or_wrong_output",
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
        "uses_arrow_instead_of_madgraph_gt",
        "uses_invalid_beam1_beam2_commands",
        "uses_invalid_beamenergies_command",
        "uses_process_keyword",
        "missing_generate_keyword",
        "uses_tbar_instead_of_t_tilde",
        "uses_words_instead_of_madgraph_antiparticle",
        "includes_explanation_not_file_only",
        "includes_reasoning_or_chat_tags",
        "echoes_prompt",
    }
    passed = (
        checks["correct_process"]
        and checks["has_output_ttbar"]
        and checks["ebeam1_6500"]
        and checks["ebeam2_6500"]
        and not hard_failures.intersection(failure_set)
    )

    return {
        "task_id": "mg_basic_002",
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
