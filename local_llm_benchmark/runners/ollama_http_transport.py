#!/usr/bin/env python3
"""Safe, non-interactive Ollama HTTP transport for HEPToolBench.

The benchmark must never capture output from ``ollama run``.  The CLI emits
terminal cursor-control sequences on some hosts; if captured literally, those
bytes can corrupt otherwise valid model artifacts.  This module uses Ollama's
non-streaming HTTP API and validates generated text before it reaches a scorer.
"""

from __future__ import annotations

import hashlib
import json
import socket
from collections import Counter
from functools import lru_cache
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TRANSPORT_NAME = "ollama_http_generate_stream_false"
DEFAULT_NUM_CTX = 4096


class OllamaTransportError(RuntimeError):
    """Infrastructure-level Ollama failure that must not be scored as a model failure."""

    def __init__(
        self,
        message: str,
        *,
        failure_mode: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.failure_mode = failure_mode
        self.metadata = metadata or {}


class OllamaTimeoutError(OllamaTransportError):
    """Ollama did not return within the configured benchmark timeout."""


class OllamaOutputContaminationError(OllamaTransportError):
    """Generated text contains forbidden terminal/control characters."""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _host_without_trailing_slash(host: str) -> str:
    normalized = host.strip().rstrip("/")
    if not normalized.startswith(("http://", "https://")):
        raise OllamaTransportError(
            f"OLLAMA_HOST must start with http:// or https://, got {host!r}.",
            failure_mode="ollama_invalid_host",
        )
    return normalized


def _request_metadata(
    *,
    host: str,
    endpoint: str,
    model: str | None,
    prompt: str | None,
    timeout: int,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "transport": TRANSPORT_NAME,
        "host": _host_without_trailing_slash(host),
        "endpoint": endpoint,
        "timeout_seconds": timeout,
    }
    if model is not None:
        metadata["requested_model"] = model
    if prompt is not None:
        metadata["prompt"] = {
            "characters": len(prompt),
            "utf8_bytes": len(prompt.encode("utf-8")),
            "sha256": sha256_text(prompt),
        }
    if payload is not None:
        metadata["request"] = {
            key: value
            for key, value in payload.items()
            if key != "prompt"
        }
    return metadata


def _json_request(
    *,
    host: str,
    endpoint: str,
    timeout: int,
    payload: dict[str, Any] | None = None,
    model: str | None = None,
    prompt: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    base = _host_without_trailing_slash(host)
    url = f"{base}{endpoint}"
    data = None
    headers = {"Accept": "application/json"}
    method = "GET"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"

    request_metadata = _request_metadata(
        host=base,
        endpoint=endpoint,
        model=model,
        prompt=prompt,
        timeout=timeout,
        payload=payload,
    )
    request = Request(url, data=data, headers=headers, method=method)

    try:
        with urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 200))
            body = response.read()
    except HTTPError as exc:
        body = exc.read()
        preview = body[:1000].decode("utf-8", errors="replace")
        request_metadata["http_status"] = exc.code
        request_metadata["error_body_preview"] = preview
        raise OllamaTransportError(
            f"Ollama HTTP {exc.code} from {endpoint}: {preview}",
            failure_mode="ollama_http_error",
            metadata=request_metadata,
        ) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise OllamaTimeoutError(
            f"Ollama request timed out after {timeout} seconds at {endpoint}.",
            failure_mode="ollama_timeout",
            metadata=request_metadata,
        ) from exc
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise OllamaTimeoutError(
                f"Ollama request timed out after {timeout} seconds at {endpoint}.",
                failure_mode="ollama_timeout",
                metadata=request_metadata,
            ) from exc
        raise OllamaTransportError(
            f"Could not reach Ollama at {base}: {exc.reason}",
            failure_mode="ollama_connection_error",
            metadata=request_metadata,
        ) from exc
    except OSError as exc:
        raise OllamaTransportError(
            f"Ollama transport failed at {base}: {exc}",
            failure_mode="ollama_connection_error",
            metadata=request_metadata,
        ) from exc

    request_metadata["http_status"] = status
    request_metadata["response_body_bytes"] = len(body)

    try:
        decoded = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise OllamaTransportError(
            "Ollama returned a response body that is not valid UTF-8.",
            failure_mode="ollama_invalid_utf8_response",
            metadata=request_metadata,
        ) from exc

    try:
        parsed = json.loads(decoded)
    except json.JSONDecodeError as exc:
        request_metadata["response_body_preview"] = decoded[:1000]
        raise OllamaTransportError(
            f"Ollama returned invalid JSON from {endpoint}: {exc}",
            failure_mode="ollama_invalid_json_response",
            metadata=request_metadata,
        ) from exc

    if not isinstance(parsed, dict):
        raise OllamaTransportError(
            f"Ollama returned {type(parsed).__name__}, expected a JSON object.",
            failure_mode="ollama_invalid_response_shape",
            metadata=request_metadata,
        )
    return parsed, request_metadata


def control_character_summary(text: str) -> dict[str, Any]:
    """Return a safe summary of forbidden C0, DEL, and C1 control characters."""

    occurrences: list[tuple[int, int]] = []
    for index, character in enumerate(text):
        codepoint = ord(character)
        if (
            (codepoint < 32 and codepoint not in (9, 10, 13))
            or 127 <= codepoint <= 159
        ):
            occurrences.append((index, codepoint))

    counts = Counter(codepoint for _, codepoint in occurrences)
    return {
        "forbidden_total": len(occurrences),
        "escape_total": counts.get(0x1B, 0),
        "by_codepoint": {
            f"U+{codepoint:04X}": count
            for codepoint, count in sorted(counts.items())
        },
        "first_positions": [
            {"character_index": index, "codepoint": f"U+{codepoint:04X}"}
            for index, codepoint in occurrences[:20]
        ],
    }


def validate_generated_text(
    text: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = control_character_summary(text)
    if summary["forbidden_total"]:
        error_metadata = dict(metadata or {})
        error_metadata["control_characters"] = summary
        raise OllamaOutputContaminationError(
            "Ollama output contains forbidden terminal/control characters; "
            "the artifact was rejected before scoring.",
            failure_mode="ollama_output_control_characters",
            metadata=error_metadata,
        )
    return summary


@lru_cache(maxsize=8)
def get_model_catalog(host: str, timeout: int = 60) -> tuple[dict[str, Any], ...]:
    data, _ = _json_request(
        host=host,
        endpoint="/api/tags",
        timeout=timeout,
    )
    models = data.get("models")
    if not isinstance(models, list):
        raise OllamaTransportError(
            "Ollama /api/tags response does not contain a models list.",
            failure_mode="ollama_invalid_tags_response",
        )
    return tuple(item for item in models if isinstance(item, dict))


def installed_model_names(host: str, timeout: int = 60) -> list[str]:
    names: list[str] = []
    for item in get_model_catalog(host, timeout):
        value = item.get("name") or item.get("model")
        if isinstance(value, str) and value:
            names.append(value)
    if not names:
        raise OllamaTransportError(
            f"No installed Ollama models were found at {host}.",
            failure_mode="ollama_no_installed_models",
        )
    return names


def clear_model_caches() -> None:
    get_model_catalog.cache_clear()
    get_model_identity.cache_clear()


@lru_cache(maxsize=128)
def get_model_identity(
    host: str,
    model: str,
    timeout: int = 60,
) -> dict[str, Any]:
    catalog_match: dict[str, Any] | None = None
    for item in get_model_catalog(host, timeout):
        candidates = {item.get("name"), item.get("model")}
        if model in candidates:
            catalog_match = dict(item)
            break

    if catalog_match is None:
        raise OllamaTransportError(
            f"Model {model!r} was not found in Ollama /api/tags at {host}.",
            failure_mode="ollama_model_identity_not_found",
        )

    show, _ = _json_request(
        host=host,
        endpoint="/api/show",
        timeout=timeout,
        payload={"model": model},
        model=model,
    )
    model_info = show.get("model_info")
    context_fields: dict[str, Any] = {}
    if isinstance(model_info, dict):
        for key, value in model_info.items():
            lowered = str(key).lower()
            if any(
                marker in lowered
                for marker in (
                    "context_length",
                    "embedding_length",
                    "block_count",
                    "parameter_count",
                )
            ):
                context_fields[str(key)] = value

    identity = {
        "requested_name": model,
        "resolved_name": catalog_match.get("name") or catalog_match.get("model"),
        "digest": catalog_match.get("digest"),
        "modified_at": catalog_match.get("modified_at"),
        "size": catalog_match.get("size"),
        "details": catalog_match.get("details"),
        "capabilities": show.get("capabilities"),
        "parameters": show.get("parameters"),
        "model_info_selected": context_fields,
    }
    for field in ("template", "modelfile"):
        value = show.get(field)
        if isinstance(value, str):
            identity[f"{field}_sha256"] = sha256_text(value)
    return identity


def generate(
    *,
    host: str,
    model: str,
    prompt: str,
    timeout: int,
    num_ctx: int = DEFAULT_NUM_CTX,
) -> tuple[str, dict[str, Any]]:
    if num_ctx < 1:
        raise OllamaTransportError(
            f"num_ctx must be positive, got {num_ctx}.",
            failure_mode="ollama_invalid_num_ctx",
        )

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_ctx": num_ctx},
    }
    data, metadata = _json_request(
        host=host,
        endpoint="/api/generate",
        timeout=timeout,
        payload=payload,
        model=model,
        prompt=prompt,
    )

    output = data.get("response")
    if not isinstance(output, str):
        raise OllamaTransportError(
            "Ollama /api/generate response has no string 'response' field.",
            failure_mode="ollama_missing_response_text",
            metadata=metadata,
        )
    if data.get("done") is not True:
        metadata["ollama_done"] = data.get("done")
        raise OllamaTransportError(
            "Non-streaming Ollama response did not finish with done=true.",
            failure_mode="ollama_incomplete_http_response",
            metadata=metadata,
        )

    response_metadata = {
        key: value
        for key, value in data.items()
        if key not in {"response", "context"}
    }
    context = data.get("context")
    if isinstance(context, list):
        response_metadata["context_token_count"] = len(context)

    metadata["response"] = response_metadata
    metadata["output"] = {
        "characters": len(output),
        "utf8_bytes": len(output.encode("utf-8")),
        "sha256": sha256_text(output),
    }
    controls = validate_generated_text(output, metadata=metadata)
    metadata["output"]["control_characters"] = controls
    metadata["model_identity"] = get_model_identity(host, model)
    return output, metadata
