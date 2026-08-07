"""Generation controls for HEPToolBench's Ollama HTTP transport."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from typing import Any

ENV_THINK = "HEPTOOLBENCH_OLLAMA_THINK"
ENV_TEMPERATURE = "HEPTOOLBENCH_OLLAMA_TEMPERATURE"
ENV_SEED = "HEPTOOLBENCH_OLLAMA_SEED"
ENV_NUM_PREDICT = "HEPTOOLBENCH_OLLAMA_NUM_PREDICT"


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"auto", "default"}:
        return None
    return text


def _normalize_think(value: Any) -> bool | str | None:
    if isinstance(value, bool):
        return value

    text = _optional_text(value)
    if text is None:
        return None

    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"low", "medium", "high", "max"}:
        return lowered

    raise ValueError(
        "--think must be auto, true, false, low, medium, high, or max."
    )


def normalize_ollama_generation_settings(
    *,
    num_ctx: Any,
    think: Any = None,
    temperature: Any = None,
    seed: Any = None,
    num_predict: Any = None,
) -> dict[str, Any]:
    normalized_num_ctx = int(num_ctx)
    if normalized_num_ctx < 1:
        raise ValueError("num_ctx must be positive.")

    normalized_temperature = None
    text = _optional_text(temperature)
    if text is not None:
        normalized_temperature = float(text)
        if normalized_temperature < 0:
            raise ValueError("--temperature must be non-negative.")

    normalized_seed = None
    text = _optional_text(seed)
    if text is not None:
        normalized_seed = int(text)

    normalized_num_predict = None
    text = _optional_text(num_predict)
    if text is not None:
        normalized_num_predict = int(text)
        if normalized_num_predict < 1:
            raise ValueError("--num-predict must be positive.")

    return {
        "num_ctx": normalized_num_ctx,
        "think": _normalize_think(think),
        "temperature": normalized_temperature,
        "seed": normalized_seed,
        "num_predict": normalized_num_predict,
    }


def current_ollama_generation_settings(num_ctx: int) -> dict[str, Any]:
    return normalize_ollama_generation_settings(
        num_ctx=num_ctx,
        think=os.environ.get(ENV_THINK),
        temperature=os.environ.get(ENV_TEMPERATURE),
        seed=os.environ.get(ENV_SEED),
        num_predict=os.environ.get(ENV_NUM_PREDICT),
    )


def ollama_generation_setting_mismatches(
    saved: Mapping[str, Any],
    requested: Mapping[str, Any],
    keys: Iterable[str],
) -> list[tuple[str, Any, Any]]:
    mismatches: list[tuple[str, Any, Any]] = []
    for key in keys:
        saved_value = saved.get(key)
        requested_value = requested.get(key)
        if saved_value != requested_value:
            mismatches.append((key, saved_value, requested_value))
    return mismatches


def get_ollama_think() -> bool | str | None:
    return _normalize_think(os.environ.get(ENV_THINK))


def build_ollama_options(num_ctx: int) -> dict[str, Any]:
    settings = current_ollama_generation_settings(num_ctx)

    options: dict[str, Any] = {"num_ctx": settings["num_ctx"]}

    for key in ("temperature", "seed", "num_predict"):
        value = settings[key]
        if value is not None:
            options[key] = value

    return options
