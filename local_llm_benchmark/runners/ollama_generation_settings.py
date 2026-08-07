"""Generation controls for HEPToolBench's Ollama HTTP transport."""

from __future__ import annotations

import os
from typing import Any

ENV_THINK = "HEPTOOLBENCH_OLLAMA_THINK"
ENV_TEMPERATURE = "HEPTOOLBENCH_OLLAMA_TEMPERATURE"
ENV_SEED = "HEPTOOLBENCH_OLLAMA_SEED"
ENV_NUM_PREDICT = "HEPTOOLBENCH_OLLAMA_NUM_PREDICT"


def _raw(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    if not value or value.lower() in {"auto", "default"}:
        return None
    return value


def get_ollama_think() -> bool | str | None:
    value = _raw(ENV_THINK)
    if value is None:
        return None

    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"low", "medium", "high", "max"}:
        return lowered

    raise ValueError(
        "--think must be auto, true, false, low, medium, high, or max."
    )


def build_ollama_options(num_ctx: int) -> dict[str, Any]:
    if int(num_ctx) < 1:
        raise ValueError("num_ctx must be positive.")

    options: dict[str, Any] = {"num_ctx": int(num_ctx)}

    temperature = _raw(ENV_TEMPERATURE)
    if temperature is not None:
        value = float(temperature)
        if value < 0:
            raise ValueError("--temperature must be non-negative.")
        options["temperature"] = value

    seed = _raw(ENV_SEED)
    if seed is not None:
        options["seed"] = int(seed)

    num_predict = _raw(ENV_NUM_PREDICT)
    if num_predict is not None:
        value = int(num_predict)
        if value < 1:
            raise ValueError("--num-predict must be positive.")
        options["num_predict"] = value

    return options
