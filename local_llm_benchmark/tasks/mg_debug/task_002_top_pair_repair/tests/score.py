#!/usr/bin/env python3
"""Score mg_debug_002 submissions."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
BASIC_SCORER = ROOT / "tasks/mg_basic/task_002_top_pair_freeform/tests/score.py"


def load_basic_scorer():
    spec = importlib.util.spec_from_file_location("mg_basic_002_score", BASIC_SCORER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load scorer: {BASIC_SCORER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def score_submission(path: Path) -> dict:
    module = load_basic_scorer()
    result = module.score_submission(path)
    result["task_id"] = "mg_debug_002"
    result["repair_target"] = "broken top-pair proc_card.dat"
    return result


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

