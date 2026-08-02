#!/usr/bin/env python3
"""
Audit HEPToolBench tasks for possible answer leakage in prompts.

This script is conservative: it flags candidates for human review.  A flag does
not automatically mean the task is invalid.  The most important flag is when
values from expected/*.json appear inside a JSON/template block in prompt.md.

Usage from repo root:
    python scripts/audit_task_leakage.py

Outputs:
    audit/task_inventory.csv
    audit/leakage_audit.csv
    audit/leakage_audit.md
    audit/review_pack/<task_id>.txt
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Iterable

TASKS_ROOT = Path("tasks")
OUT_ROOT = Path("audit")

FENCE_RE = re.compile(r"```(?:json|JSON|python|bash|text|txt|dat|md)?\s*\n(.*?)```", re.S)
BRACE_BLOCK_RE = re.compile(r"\{[\s\S]*?\}", re.S)

GENERIC_VALUES = {
    "true", "false", "null", "none", "yes", "no", "ok", "pass", "fail",
    "success", "failed", "valid", "invalid", "warning", "error", "low", "high",
    "medium", "string", "number", "integer", "float", "boolean", "array",
    "object", "required", "optional", "unknown", "na", "n/a",
}


def read_text(path: Path) -> str:
    try:
        return path.read_text(errors="ignore")
    except Exception:
        return ""


def load_json(path: Path) -> Any | None:
    try:
        return json.loads(read_text(path))
    except Exception:
        return None


def metadata_for(task_dir: Path) -> dict[str, Any]:
    data = load_json(task_dir / "metadata.json")
    return data if isinstance(data, dict) else {}


def extract_leaf_values(obj: Any) -> list[str]:
    vals: list[str] = []
    if isinstance(obj, dict):
        for v in obj.values():
            vals.extend(extract_leaf_values(v))
    elif isinstance(obj, list):
        for v in obj:
            vals.extend(extract_leaf_values(v))
    elif isinstance(obj, (str, int, float)) and not isinstance(obj, bool):
        s = str(obj).strip()
        if is_informative_value(s):
            vals.append(s)
    return vals


def is_informative_value(s: str) -> bool:
    t = s.strip().strip('"\'')
    if not t:
        return False
    if t.lower() in GENERIC_VALUES:
        return False
    if len(t) < 3:
        return False
    # Skip pure tiny numbers, but keep physically meaningful values like 6500, 13000, 10000.
    if re.fullmatch(r"[-+]?\d+(\.\d+)?", t):
        try:
            x = abs(float(t))
            if x in {0, 1, 2}:
                return False
        except Exception:
            pass
    # Skip placeholder-like entries.
    if "<" in t and ">" in t:
        return False
    return True


def unique_preserve(xs: Iterable[str]) -> list[str]:
    seen = set()
    out = []
    for x in xs:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def prompt_blocks(prompt: str) -> list[str]:
    blocks = FENCE_RE.findall(prompt)
    # Add brace blocks too; useful when prompt contains an inline JSON object not fenced.
    blocks.extend(BRACE_BLOCK_RE.findall(prompt))
    return unique_preserve([b.strip() for b in blocks if b.strip()])


def looks_like_json_template(block: str) -> bool:
    b = block.strip()
    if not ("{" in b and "}" in b):
        return False
    # It need not parse as JSON; schema examples can have comments/placeholders.
    jsonish_tokens = [":", "\"", "[", "]", "{" , "}"]
    return sum(tok in b for tok in jsonish_tokens) >= 4


def expected_values(task_dir: Path) -> tuple[list[str], list[str]]:
    vals: list[str] = []
    sources: list[str] = []
    expected_dir = task_dir / "expected"
    if not expected_dir.exists():
        return [], []

    for p in sorted(expected_dir.rglob("*")):
        if not p.is_file():
            continue
        txt = read_text(p)
        if p.suffix.lower() == ".json":
            data = load_json(p)
            if data is not None:
                for v in extract_leaf_values(data):
                    vals.append(v)
                    sources.append(str(p))
        else:
            # For non-JSON expected files, use informative non-comment lines.
            for line in txt.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if is_informative_value(line):
                    vals.append(line)
                    sources.append(str(p))
    return unique_preserve(vals), sources


def find_overlaps(values: list[str], text: str) -> list[str]:
    low = text.lower()
    hits = []
    for v in values:
        vv = v.strip()
        if not vv:
            continue
        if vv.lower() in low:
            hits.append(vv)
    return unique_preserve(hits)


def score_pass_lines(score_path: Path) -> list[str]:
    lines = read_text(score_path).splitlines()
    out = []
    for i, line in enumerate(lines, start=1):
        low = line.lower()
        if "passed" in low or "threshold" in low or "score >=" in low or "score>=" in low:
            out.append(f"L{i}: {line.rstrip()}")
    return out[:40]


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    review_dir = OUT_ROOT / "review_pack"
    review_dir.mkdir(parents=True, exist_ok=True)

    task_dirs = sorted(p for p in TASKS_ROOT.glob("*/*") if (p / "prompt.md").exists())
    rows = []
    inventory_rows = []

    for task_dir in task_dirs:
        meta = metadata_for(task_dir)
        task_id = meta.get("task_id", task_dir.name)
        mode = meta.get("mode", "")
        category = meta.get("category", task_dir.parent.name)
        prompt = read_text(task_dir / "prompt.md")
        blocks = prompt_blocks(prompt)
        jsonish_blocks = [b for b in blocks if looks_like_json_template(b)]
        exp_vals, _ = expected_values(task_dir)

        block_hits: list[str] = []
        for b in jsonish_blocks:
            block_hits.extend(find_overlaps(exp_vals, b))
        block_hits = unique_preserve(block_hits)
        prompt_hits = find_overlaps(exp_vals, prompt)

        expected_files = sorted(str(p.relative_to(task_dir)) for p in (task_dir / "expected").rglob("*") if p.is_file()) if (task_dir / "expected").exists() else []
        input_files = sorted(str(p.relative_to(task_dir)) for p in (task_dir / "input").rglob("*") if p.is_file()) if (task_dir / "input").exists() else []
        artifact = meta.get("artifact") or ";".join(meta.get("expected_artifacts", [])) if isinstance(meta.get("expected_artifacts"), list) else meta.get("expected_artifacts", "")

        status = "probably_clean"
        reason = "no expected values found inside prompt JSON/template block"
        if block_hits:
            status = "REVIEW_LEAKAGE"
            reason = "expected output values appear inside a JSON/template block in prompt.md"
        elif prompt_hits and ("json" in str(mode).lower() or task_dir.name.endswith("_json")):
            status = "review_context"
            reason = "expected values appear somewhere in prompt; may be legitimate input context, but review"

        rows.append({
            "task_id": task_id,
            "task_dir": str(task_dir),
            "category": category,
            "mode": mode,
            "artifact": artifact,
            "status_suggestion": status,
            "reason": reason,
            "num_jsonish_prompt_blocks": len(jsonish_blocks),
            "num_expected_values": len(exp_vals),
            "expected_values_inside_prompt_blocks_count": len(block_hits),
            "expected_values_inside_prompt_blocks_sample": "; ".join(block_hits[:20]),
            "expected_values_anywhere_in_prompt_count": len(prompt_hits),
            "expected_values_anywhere_in_prompt_sample": "; ".join(prompt_hits[:20]),
            "input_files": ";".join(input_files),
            "expected_files": ";".join(expected_files),
        })

        inventory_rows.append({
            "task_id": task_id,
            "task_dir": str(task_dir),
            "category": category,
            "mode": mode,
            "artifact": artifact,
            "description": meta.get("description", ""),
            "input_files": ";".join(input_files),
            "expected_files": ";".join(expected_files),
        })

        # Review pack text file.
        rp = review_dir / f"{task_id}.txt"
        with rp.open("w") as f:
            f.write("=" * 100 + "\n")
            f.write(f"TASK: {task_id}\n")
            f.write(f"DIR:  {task_dir}\n")
            f.write(f"MODE: {mode}\n")
            f.write(f"STATUS SUGGESTION: {status}\n")
            f.write(f"REASON: {reason}\n")
            f.write("=" * 100 + "\n\n")
            f.write("METADATA\n--------\n")
            f.write(json.dumps(meta, indent=2) + "\n\n")
            f.write("PROMPT.md\n---------\n")
            f.write(prompt + "\n\n")
            if input_files:
                f.write("INPUT FILES\n-----------\n")
                for rel in input_files:
                    f.write(f"\n--- {rel} ---\n")
                    f.write(read_text(task_dir / rel) + "\n")
                f.write("\n")
            if expected_files:
                f.write("EXPECTED FILES\n--------------\n")
                for rel in expected_files:
                    f.write(f"\n--- {rel} ---\n")
                    f.write(read_text(task_dir / rel) + "\n")
                f.write("\n")
            f.write("SCORER PASS/THRESHOLD LINES\n---------------------------\n")
            for line in score_pass_lines(task_dir / "tests" / "score.py"):
                f.write(line + "\n")
            f.write("\n")
            f.write("EXPECTED VALUES INSIDE PROMPT TEMPLATE BLOCKS\n---------------------------------------------\n")
            for h in block_hits:
                f.write(f"- {h}\n")

    # Write CSVs.
    inv_path = OUT_ROOT / "task_inventory.csv"
    with inv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(inventory_rows[0].keys()) if inventory_rows else [])
        writer.writeheader()
        writer.writerows(inventory_rows)

    audit_path = OUT_ROOT / "leakage_audit.csv"
    with audit_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    # Markdown summary.
    md_path = OUT_ROOT / "leakage_audit.md"
    flagged = [r for r in rows if r["status_suggestion"] == "REVIEW_LEAKAGE"]
    review = [r for r in rows if r["status_suggestion"] == "review_context"]
    with md_path.open("w") as f:
        f.write("# HEPToolBench leakage audit\n\n")
        f.write("This is an automated conservative audit. Human review is still required.\n\n")
        f.write("## Strong candidates: expected values inside prompt template blocks\n\n")
        if not flagged:
            f.write("None found.\n\n")
        else:
            f.write("| task_id | mode | reason | sample overlapping values |\n")
            f.write("|---|---|---|---|\n")
            for r in flagged:
                sample = r["expected_values_inside_prompt_blocks_sample"].replace("|", "\\|")
                f.write(f"| {r['task_id']} | {r['mode']} | {r['reason']} | {sample} |\n")
            f.write("\n")
        f.write("## Context review candidates: expected values somewhere in prompt\n\n")
        if not review:
            f.write("None found.\n\n")
        else:
            f.write("| task_id | mode | reason | sample overlapping values |\n")
            f.write("|---|---|---|---|\n")
            for r in review:
                sample = r["expected_values_anywhere_in_prompt_sample"].replace("|", "\\|")
                f.write(f"| {r['task_id']} | {r['mode']} | {r['reason']} | {sample} |\n")
            f.write("\n")
        f.write("## All task statuses\n\n")
        f.write("| task_id | status | prompt blocks | expected values | block-hit count |\n")
        f.write("|---|---:|---:|---:|---:|\n")
        for r in rows:
            f.write(f"| {r['task_id']} | {r['status_suggestion']} | {r['num_jsonish_prompt_blocks']} | {r['num_expected_values']} | {r['expected_values_inside_prompt_blocks_count']} |\n")

    print("Saved:")
    print(" ", inv_path)
    print(" ", audit_path)
    print(" ", md_path)
    print(" ", review_dir)
    print()
    print(f"Tasks audited: {len(rows)}")
    print(f"Strong leakage candidates: {len(flagged)}")
    print(f"Context review candidates: {len(review)}")
    print()
    print("Strong candidates:")
    for r in flagged:
        print(" -", r["task_id"], "=>", r["expected_values_inside_prompt_blocks_sample"][:160])


if __name__ == "__main__":
    main()
