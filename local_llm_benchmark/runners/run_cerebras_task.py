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


def safe_model_name(model: str) -> str:
    return (
        model.replace("/", "_")
        .replace(":", "_")
        .replace(".", "_")
        .replace("-", "-")
        + "_cerebras"
    )


def call_cerebras_rest(model: str, prompt: str, timeout: int, temperature: float, max_tokens: int):
    key = os.environ.get("CEREBRAS_API_KEY")
    if not key:
        raise RuntimeError("CEREBRAS_API_KEY is not set")

    url = "https://api.cerebras.ai/v1/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }

    payload = {
        "model": model,
        "stream": False,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": 0.95,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are being evaluated in a particle-physics software benchmark. "
                    "Return only the requested output artifact. "
                    "Do not include explanations, markdown fences, commentary, or reasoning."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    }

    r = requests.post(url, headers=headers, json=payload, timeout=timeout)

    if not r.ok:
        raise RuntimeError(f"Cerebras API error {r.status_code}: {r.text[:2000]}")

    data = r.json()

    try:
        output = data["choices"][0]["message"]["content"] or ""
    except Exception:
        raise RuntimeError(
            "Could not extract content from Cerebras response: "
            + json.dumps(data)[:2000]
        )

    output = output.strip()

    if not output:
        raise RuntimeError("Cerebras returned empty output: " + json.dumps(data)[:2000])

    low = output.lower()
    bad_phrases = [
        "rate limit",
        "quota",
        "insufficient",
        "credit",
        "billing",
        "too many requests",
        "unauthorized",
        "permission",
        "not allowed",
        "model not found",
    ]

    if any(x in low for x in bad_phrases):
        raise RuntimeError("Cerebras/provider limit/access message detected in output")

    return output, data


def run_evaluator(task: str, submission_path: Path, outpath: Path):
    cmd = [
        sys.executable,
        str(ROOT / "runners" / "evaluate_submission.py"),
        "--task", task,
        "--submission", str(submission_path),
        "--output", str(outpath),
    ]

    proc = subprocess.run(cmd, text=True, capture_output=True)

    if proc.returncode != 0:
        return {
            "task_id": task,
            "score": 0.0,
            "passed": False,
            "failure_modes": ["evaluation_failed"],
            "evaluator_stdout": proc.stdout[-2000:],
            "evaluator_stderr": proc.stderr[-4000:],
        }

    if not outpath.exists():
        return {
            "task_id": task,
            "score": 0.0,
            "passed": False,
            "failure_modes": ["evaluation_output_missing"],
        }

    return json.loads(outpath.read_text(encoding="utf-8"))


def main():
    ensure_output_dirs()
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="zai-glm-4.7")
    ap.add_argument("--task", required=True)
    ap.add_argument("--timeout", type=int, default=1200)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=8192)
    args = ap.parse_args()

    safe = safe_model_name(args.model)

    print(f"[run] {args.model} -> {args.task}", flush=True)

    try:
        if args.task not in base.TASKS:
            raise RuntimeError(f"Unknown task: {args.task}")

        artifact = base.TASKS[args.task]["artifact"]

        subdir = ROOT / "submissions" / safe / args.task
        subdir.mkdir(parents=True, exist_ok=True)

        submission_path = subdir / artifact
        answer_txt = subdir / "answer.txt"
        raw_response_path = subdir / "cerebras_raw_response.json"

        outpath = ROOT / "results" / f"{safe}_{args.task}.json"
        outpath.parent.mkdir(parents=True, exist_ok=True)

        if submission_path.exists() and submission_path.stat().st_size > 0:
            print(f"[reuse] existing artifact: {submission_path}", flush=True)
        else:
            prompt = base.build_prompt(args.task)

            output, raw = call_cerebras_rest(
                model=args.model,
                prompt=prompt,
                timeout=args.timeout,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
            )

            submission_path.write_text(output.strip() + "\n", encoding="utf-8")
            answer_txt.write_text(output.strip() + "\n", encoding="utf-8")
            raw_response_path.write_text(
                json.dumps(raw, indent=2, sort_keys=True, default=str),
                encoding="utf-8",
            )

            print(f"[saved artifact] {submission_path}", flush=True)

        result = run_evaluator(args.task, submission_path, outpath)

        result.update({
            "model": args.model,
            "safe_model": safe,
            "task_id": args.task,
            "api": "cerebras",
            "answer_path": str(submission_path),
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
