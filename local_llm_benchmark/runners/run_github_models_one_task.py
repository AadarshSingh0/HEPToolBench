#!/usr/bin/env python3
import argparse
import json
import os
import sys
import traceback
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runners"))
import run_ollama_task as base

ROOT = Path(__file__).resolve().parents[1]

def safe_model_name(model):
    return model.replace("/", "_").replace(":", "_").replace(".", "_").replace("-", "-") + "_github_models"

def call_github_models(prompt, model, timeout):
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not set")

    url = "https://models.github.ai/inference/chat/completions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are being evaluated in a particle-physics software benchmark. "
                    "Return only the requested output file content. "
                    "Do not include explanations, markdown fences, or commentary."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
    }

    r = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if not r.ok:
        raise RuntimeError(f"GitHub Models API error {r.status_code}: {r.text[:2000]}")

    data = r.json()
    return data["choices"][0]["message"]["content"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="openai/gpt-4o-mini")
    ap.add_argument("--task", required=True)
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    task_id = args.task
    model = args.model
    model_id = safe_model_name(model)

    prompt = base.build_prompt(task_id)
    artifact = base.TASKS[task_id]["artifact"]

    subdir = ROOT / "submissions" / model_id / task_id
    subdir.mkdir(parents=True, exist_ok=True)

    submission = subdir / artifact
    stderr = subdir / "github_models_stderr.txt"
    result_path = ROOT / "results" / f"{model_id}_{task_id}.json"

    print(f"[run] {model} -> {task_id}")

    try:
        text = call_github_models(prompt, model, args.timeout)
        submission.write_text(text.strip() + "\n")
        stderr.write_text("")
    except Exception as e:
        stderr.write_text(traceback.format_exc())
        result = {
            "task_id": task_id,
            "model": model,
            "score": 0.0,
            "passed": False,
            "failure_modes": ["github_models_api_error"],
            "error": str(e),
        }
        result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print("[error]", e)
        return

    result = base.evaluate(task_id, submission, result_path)
    result["model"] = model
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

    print(f"[score] {task_id}: score={result.get('score')} passed={result.get('passed')}")
    print(f"[saved] {result_path}")

if __name__ == "__main__":
    main()
