#!/usr/bin/env python3
import argparse
import json
import os
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
    return model.replace("/", "_").replace(":", "_").replace(".", "_").replace("-", "-") + "_sarvam_api"

def call_sarvam(prompt, model, timeout):
    api_key = os.environ.get("SARVAM_API_KEY")
    if not api_key:
        raise RuntimeError("SARVAM_API_KEY is not set")

    url = "https://api.sarvam.ai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Return only the requested output file content. Do not include explanations or markdown fences."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0,
        "reasoning_effort": os.environ.get("SARVAM_REASONING_EFFORT", "low"),
        "max_tokens": int(os.environ.get("SARVAM_MAX_TOKENS", "16384"))
    }

    print(f"[sarvam_config] model={model} max_tokens={payload.get('max_tokens')} reasoning_effort={payload.get('reasoning_effort')}")
    r = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if not r.ok:
        raise RuntimeError(f"Sarvam API error {r.status_code}: {r.text[:2000]}")

    data = r.json()
    def _extract_text_value(value):
        """Extract textual content from OpenAI-compatible content fields.

        Some APIs return message.content as a string, while others may return
        a list of typed content blocks such as [{"type":"text","text":"..."}].
        If content is genuinely missing/None, return None so the caller can
        mark the run as an API/runner failure rather than crashing on .strip().
        """
        if value is None:
            return None
        if isinstance(value, str):
            return value if value.strip() else None
        if isinstance(value, list):
            parts = []
            for item in value:
                t = _extract_text_value(item)
                if t and t.strip():
                    parts.append(t)
            return "\n".join(parts) if parts else None
        if isinstance(value, dict):
            # Prefer explicit text-bearing fields only; do not recursively grab
            # arbitrary metadata like model names.
            for key in ("text", "content", "output_text", "value"):
                if key in value:
                    t = _extract_text_value(value.get(key))
                    if t and t.strip():
                        return t
        return None

    choice0 = None
    try:
        choices = data.get("choices", []) if isinstance(data, dict) else []
        if choices:
            choice0 = choices[0]
    except Exception:
        choice0 = None

    text = None
    if isinstance(choice0, dict):
        msg = choice0.get("message")
        if isinstance(msg, dict):
            text = _extract_text_value(msg.get("content"))
        if text is None:
            text = _extract_text_value(choice0.get("text"))

    if text is None and isinstance(data, dict):
        for key in ("output_text", "content", "response", "text"):
            text = _extract_text_value(data.get(key))
            if text and text.strip():
                break

    if text is None or not str(text).strip():
        preview = json.dumps(data, ensure_ascii=False)[:2500]
        raise RuntimeError("Sarvam API returned empty/null message content. Response preview: " + preview)

    return str(text)

def main():
    ensure_output_dirs()
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.environ.get("SARVAM_MODEL", "sarvam-105b"))
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
    stderr = subdir / "sarvam_stderr.txt"
    result_path = ROOT / "results" / f"{model_id}_{task_id}.json"

    print(f"[run] {model} -> {task_id}")

    try:
        text = call_sarvam(prompt, model, args.timeout)
        if text is None or not str(text).strip():
            raise RuntimeError("Sarvam runner got empty text after API call")
        submission.write_text(str(text).strip() + "\n")
        stderr.write_text("")
    except Exception as e:
        stderr.write_text(traceback.format_exc())
        result = {
            "task_id": task_id,
            "model": model,
            "score": 0.0,
            "passed": False,
            "failure_modes": ["sarvam_api_error"],
            "error": str(e)
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
