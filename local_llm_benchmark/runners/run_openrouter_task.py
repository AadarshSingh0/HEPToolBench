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
        + "_openrouter"
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
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                btype = str(block.get("type", "")).lower()
                if btype in {"reasoning", "thinking"}:
                    continue
                if "text" in block:
                    parts.append(str(block.get("text", "")))
        return "\n".join(p for p in parts if p.strip()).strip()

    return str(content)

def call_openrouter(prompt, model, timeout, max_tokens):
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/HEPToolBench",
        "X-Title": "HEPToolBench",
    }

    # Model-aware reasoning config:
    # Cohere North returned content only when reasoning was enabled.
    # Other OpenRouter free models may return empty visible content if reasoning is forced.
    reasoning_config = (
        {"enabled": True}
        if (
            model.startswith("cohere/north-mini-code")
            or model.startswith("liquid/lfm-2.5-1.2b-thinking")
        )
        else {"enabled": False, "exclude": True}
    )

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Return only the requested benchmark artifact. "
                    "No explanation. No markdown. No reasoning. "
                    "If a file is requested, output only that file content."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": max_tokens,
        "reasoning": reasoning_config,
    }

    r = requests.post(url, headers=headers, json=payload, timeout=timeout)

    if not r.ok:
        raise RuntimeError(f"OpenRouter API error {r.status_code}: {r.text[:2000]}")

    data = r.json()
    msg = data["choices"][0]["message"]
    return extract_visible_text(msg), data

def evaluate_or_zero(task, submission_path, outpath, extra_failure_modes=None):
    extra_failure_modes = extra_failure_modes or []

    try:
        result = base.evaluate(task, submission_path, outpath)
    except Exception:
        cmd = [
            sys.executable,
            str(ROOT / "runners" / "evaluate_submission.py"),
            "--task", task,
            "--submission", str(submission_path),
            "--output", str(outpath),
        ]
        proc = subprocess.run(cmd, text=True, capture_output=True)
        if proc.returncode == 0 and outpath.exists():
            result = json.loads(outpath.read_text(encoding="utf-8"))
        else:
            result = {
                "task_id": task,
                "score": 0.0,
                "passed": False,
                "failure_modes": ["evaluation_failed"],
                "evaluator_stdout": proc.stdout[-1000:] if "proc" in locals() else "",
                "evaluator_stderr": proc.stderr[-2000:] if "proc" in locals() else traceback.format_exc(),
            }

    fms = result.get("failure_modes", [])
    if not isinstance(fms, list):
        fms = [str(fms)]
    for fm in extra_failure_modes:
        if fm not in fms:
            fms.append(fm)
    result["failure_modes"] = fms
    return result

def main():
    ensure_output_dirs()
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--max-tokens", type=int, default=1024)
    args = ap.parse_args()

    safe = safe_model_name(args.model)

    print(f"[run] {args.model} -> {args.task}", flush=True)

    try:
        artifact = base.TASKS[args.task]["artifact"]

        subdir = ROOT / "submissions" / safe / args.task
        subdir.mkdir(parents=True, exist_ok=True)

        submission_path = subdir / artifact
        answer_txt = subdir / "answer.txt"
        raw_response_path = subdir / "openrouter_raw_response.json"

        outpath = ROOT / "results" / f"{safe}_{args.task}.json"
        outpath.parent.mkdir(parents=True, exist_ok=True)

        extra_fms = []

        if submission_path.exists() and submission_path.stat().st_size > 0:
            print(f"[reuse] existing artifact: {submission_path}", flush=True)
        else:
            prompt = base.build_prompt(args.task)
            output, raw = call_openrouter(
                prompt=prompt,
                model=args.model,
                timeout=args.timeout,
                max_tokens=args.max_tokens,
            )

            raw_response_path.write_text(json.dumps(raw, indent=2, sort_keys=True), encoding="utf-8")

            finish = None
            native_finish = None
            try:
                finish = raw["choices"][0].get("finish_reason")
                native_finish = raw["choices"][0].get("native_finish_reason")
            except Exception:
                pass

            if not output.strip():
                print("[empty_output] OpenRouter returned no visible content; scoring empty artifact as model/interface failure.", flush=True)
                extra_fms.append("openrouter_empty_visible_content")
                if finish:
                    extra_fms.append(f"finish_reason_{finish}")
                if native_finish:
                    extra_fms.append(f"native_finish_reason_{native_finish}")

            submission_path.write_text(output.strip() + "\n", encoding="utf-8")
            answer_txt.write_text(output.strip() + "\n", encoding="utf-8")

            print(f"[saved artifact] {submission_path}", flush=True)

        result = evaluate_or_zero(args.task, submission_path, outpath, extra_fms)

        result.update({
            "model": args.model,
            "safe_model": safe,
            "task_id": args.task,
            "api": "openrouter",
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
