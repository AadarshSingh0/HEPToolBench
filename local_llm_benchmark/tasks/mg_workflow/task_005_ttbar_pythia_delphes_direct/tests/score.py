#!/usr/bin/env python3
"""Score mg_workflow_005 submissions."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


TASK_ID = "mg_workflow_005"


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


def parse_set(name: str, text: str) -> float | None:
    match = re.search(rf"^\s*set\s+{name}\s+([0-9.eE+-]+)", text, re.IGNORECASE | re.MULTILINE)
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
        "correct_proton_definition": has_line(r"^define p = g u c d s u~ c~ d~ s~$", text),
        "correct_process": has_line(r"^generate p p > t t~$", text),
        "has_output": has_line(r"^output TTbar_P8_Delphes$", text),
        "has_launch": has_line(r"^launch$", text),
        "shower_pythia8": has_line(r"^shower\s*=\s*Pythia8$", text),
        "detector_delphes": has_line(r"^detector\s*=\s*Delphes$", text),
        "analysis_off": has_line(r"^analysis\s*=\s*OFF$", text),
        "madspin_off": has_line(r"^madspin\s*=\s*OFF$", text),
        "has_done": has_line(r"^done$", text),
        "nevents_10000": parse_set("nevents", text) == 10000.0,
        "iseed_42": parse_set("iseed", text) == 42.0,
        "ebeam1_6500": parse_set("ebeam1", text) == 6500.0,
        "ebeam2_6500": parse_set("ebeam2", text) == 6500.0,
        "no_markdown_fence": "```" not in raw,
        "no_reasoning_tags": not re.search(r"</?think>|<\|im_start\|>|<\|endoftext\|>", raw, re.IGNORECASE),
        "no_prompt_echo": "TASK INSTRUCTION:" not in raw,
        "no_long_explanation": not re.search(
            r"following|therefore|workflow settings|showering enabled|detector simulation|MadSpin disabled|completed MG5",
            raw,
            re.IGNORECASE,
        ),
    }

    if has_line(r"^p p > t t~$", text):
        failures.append("missing_generate_keyword")
    if has_line(r"^generate p p > t tbar$", text) or has_line(r"^p p > t tbar$", text):
        failures.append("uses_tbar_instead_of_t_tilde")
    if has_line(r"->", text):
        failures.append("uses_arrow_instead_of_madgraph_gt")
    if has_line(r"^process\b", text):
        failures.append("uses_process_keyword")
    if has_line(r"^set\s+shower\b", text):
        failures.append("uses_set_shower_instead_of_launch_switch")
    if has_line(r"^set\s+detector\b", text):
        failures.append("uses_set_detector_instead_of_launch_switch")
    if has_line(r"^set\s+madspin\b", text):
        failures.append("uses_set_madspin_instead_of_launch_switch")
    if has_line(r"pythia\s*=\s*on", text) or has_line(r"delphes\s*=\s*on", text):
        failures.append("uses_boolean_tool_switch_instead_of_tool_name")
    if parse_set("ebeam1", text) == 13000.0 or parse_set("ebeam2", text) == 13000.0:
        failures.append("uses_total_energy_as_each_beam")

    required_failure_map = {
        "imports_sm": "missing_import_model",
        "correct_proton_definition": "wrong_or_missing_proton_definition",
        "correct_process": "missing_or_wrong_process",
        "has_output": "missing_or_wrong_output",
        "has_launch": "missing_launch",
        "shower_pythia8": "wrong_or_missing_shower",
        "detector_delphes": "wrong_or_missing_detector",
        "analysis_off": "wrong_or_missing_analysis",
        "madspin_off": "wrong_or_missing_madspin",
        "has_done": "missing_done",
        "nevents_10000": "wrong_or_missing_nevents",
        "iseed_42": "wrong_or_missing_iseed",
        "ebeam1_6500": "wrong_or_missing_ebeam1",
        "ebeam2_6500": "wrong_or_missing_ebeam2",
    }
    for check, failure in required_failure_map.items():
        if not checks[check]:
            failures.append(failure)

    if not checks["no_markdown_fence"]:
        failures.append("includes_markdown_fence")
    if not checks["no_reasoning_tags"]:
        failures.append("includes_reasoning_or_chat_tags")
    if not checks["no_prompt_echo"]:
        failures.append("echoes_prompt")
    if not checks["no_long_explanation"]:
        failures.append("includes_explanation_not_file_only")

    weights = {
        "imports_sm": 0.06,
        "correct_proton_definition": 0.06,
        "correct_process": 0.16,
        "has_output": 0.06,
        "has_launch": 0.05,
        "shower_pythia8": 0.12,
        "detector_delphes": 0.12,
        "analysis_off": 0.02,
        "madspin_off": 0.08,
        "has_done": 0.02,
        "nevents_10000": 0.06,
        "iseed_42": 0.04,
        "ebeam1_6500": 0.06,
        "ebeam2_6500": 0.06,
        "no_markdown_fence": 0.01,
        "no_reasoning_tags": 0.01,
        "no_prompt_echo": 0.005,
        "no_long_explanation": 0.005,
    }
    score = sum(weight for key, weight in weights.items() if checks[key])

    failure_set = set(failures)
    formatting_failures = {
        "includes_markdown_fence",
        "includes_explanation_not_file_only",
        "includes_reasoning_or_chat_tags",
        "echoes_prompt",
    }
    if formatting_failures.intersection(failure_set):
        score = min(score, 0.75)

    hard_failures = formatting_failures | {
        "missing_or_wrong_process",
        "wrong_or_missing_shower",
        "wrong_or_missing_detector",
        "missing_done",
        "wrong_or_missing_madspin",
        "wrong_or_missing_ebeam1",
        "wrong_or_missing_ebeam2",
        "missing_generate_keyword",
        "uses_tbar_instead_of_t_tilde",
        "uses_arrow_instead_of_madgraph_gt",
        "uses_process_keyword",
    }
    passed = (
        all(checks[key] for key in required_failure_map)
        and not hard_failures.intersection(failure_set)
    )

    return {
        "task_id": TASK_ID,
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
