#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path
try:
    from runners.io_utils import ensure_output_dirs
except ModuleNotFoundError:
    from io_utils import ensure_output_dirs

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runners"))
import run_ollama_task as base

ROOT = Path(__file__).resolve().parents[1]

def safe_model_name(model):
    return (
        model.replace("/", "_")
        .replace(":", "_")
        .replace(".", "_")
        .replace("-", "-")
        + "_mistral_api"
    )

def extract_visible_text(message):
    content = message.get("content")

    if content is None:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
                elif "text" in block and block.get("type") != "thinking":
                    parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(p for p in parts if p.strip()).strip()

    return str(content)

def call_mistral(prompt, model, timeout, max_tokens=4096):
    key = os.environ.get("MISTRAL_API_KEY")
    if not key:
        raise RuntimeError("MISTRAL_API_KEY is not set")

    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are answering a HEP software benchmark. "
                    "Return only the requested output artifact. "
                    "Do not include explanations, markdown fences, commentary, or reasoning."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }

    r = requests.post(url, headers=headers, json=payload, timeout=timeout)

    if not r.ok:
        raise RuntimeError(f"Mistral API error {r.status_code}: {r.text[:2000]}")

    data = r.json()
    output = extract_visible_text(data["choices"][0]["message"])

    if not output.strip():
        raise RuntimeError(f"Mistral returned empty visible content: {json.dumps(data)[:2000]}")

    return output

def run_evaluator(task, answer_path, subdir, outpath):
    candidates = [answer_path, subdir]
    errors = []

    for candidate in candidates:
        if outpath.exists():
            outpath.unlink()

        cmd = [
            sys.executable,
            str(ROOT / "runners" / "evaluate_submission.py"),
            "--task", task,
            "--submission", str(candidate),
            "--output", str(outpath),
        ]

        proc = subprocess.run(cmd, text=True, capture_output=True)

        if proc.returncode == 0 and outpath.exists():
            result = json.loads(outpath.read_text(encoding="utf-8"))
            result["_submission_argument_used"] = str(candidate)
            return result

        errors.append({
            "candidate": str(candidate),
            "returncode": proc.returncode,
            "stdout": proc.stdout[-2000:],
            "stderr": proc.stderr[-4000:],
        })

    print("[evaluator failed for all candidates]")
    print(json.dumps(errors, indent=2))
    raise RuntimeError("Evaluator failed for both answer.txt and submission directory")

def main():
    ensure_output_dirs()
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--max-tokens", type=int, default=4096)
    args = ap.parse_args()

    safe = safe_model_name(args.model)
    print(f"[run] {args.model} -> {args.task}", flush=True)

    try:
        subdir = ROOT / "submissions" / safe / args.task
        subdir.mkdir(parents=True, exist_ok=True)

        answer_path = subdir / "answer.txt"
        outpath = ROOT / "results" / f"{safe}_{args.task}.json"
        outpath.parent.mkdir(parents=True, exist_ok=True)

        if answer_path.exists() and answer_path.stat().st_size > 0:
            print(f"[reuse] existing answer: {answer_path}", flush=True)
        else:
            prompt = base.build_prompt(args.task)
            output = call_mistral(
                prompt=prompt,
                model=args.model,
                timeout=args.timeout,
                max_tokens=args.max_tokens,
            )
            answer_path.write_text(output, encoding="utf-8")
            print(f"[saved answer] {answer_path}", flush=True)

        result = run_evaluator(args.task, answer_path, subdir, outpath)

        result.update({
            "model": args.model,
            "safe_model": safe,
            "task_id": args.task,
            "api": "mistral",
            "answer_path": str(answer_path),
        })

        outpath.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

        print(f"[score] {args.task}: score={result.get('score')} passed={result.get('passed')}", flush=True)
        print(f"[saved] {outpath}", flush=True)

    except Exception as e:
        print(f"[error] {e}", flush=True)
        traceback.print_exc()
        sys.exit(2)

if __name__ == "__main__":
    main()
