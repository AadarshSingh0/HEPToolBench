# Sarvam-105B recovery report

## Summary

HEPToolBench v1.2 contained four Sarvam-105B records with score 0.0 and
`passed = False` that were **not model failures**. The provider returned HTTP 400
`invalid_request_error` and no model output was ever generated. All four now carry
genuine model output and valid scores, which is why the approved `S2` policy
(exclude the entire Sarvam deployment) is superseded here by `S1R` (retain it).

## The four corrected tasks

| Task | v1.2 record | Corrected score | Passed | Origin | Artifact sha256 |
|---|---|---:|---|---|---|
| `benchmark_recommendation_018` | HTTP 400, 0.0 | **0.95** | **yes** | regenerated 2026-08-28 | `0f1a69aab5821f2c4aaa2ea87e1ba539c8d33a885131f44b4da79450a133f328` |
| `mg_runcard_004` | HTTP 400, 0.0 | 0.720 | no | regenerated 2026-08-28 | `d414734411cab7b950a148c2c3cfdd6ee9640e2ff7c2a0d5a07ebae006d3c077` |
| `mg_basic_002` | HTTP 400, 0.0 | 0.075 | no | regenerated 2026-08-28 | `95b5db72acaa0812cb9c6e22dc03d58df2446ea725ae8f6b176a5b862725a277` |
| `mg_basic_003` | HTTP 400, 0.0 | 0.075 | no | preserved output, run of 2026-06-29 | `0762ed2d0562fc5b2a212ea09a83f0ef02111c35e7297bad44e68c919172ae8a` |

A fifth Sarvam row changed for a different reason: `mg_workflow_005` was rescored
0.42 -> 0.460 by W1, from its preserved v1.2 output
(sha256 `8704ef6c496a09b4f8c7b405a4951e8ad78fdb7960a0cc171959d6e70be0946c`).
That is a scorer correction, not a recovery.

## Request configuration

Identical for all regenerations, and identical to the configuration that produced
the 27 retained Sarvam outputs:

| field | value |
|---|---|
| endpoint | Sarvam OpenAI-compatible `/v1/chat/completions` |
| model | `sarvam-105b` |
| `temperature` | 0 |
| `reasoning_effort` | `low` |
| `max_tokens` | 4096 |
| system prompt | unchanged from v1.2 |

Reasoning was **not** disabled and the token cap was **not** raised. The original
HTTP-400 failures were caused by a later rescue attempt that forced
`max_tokens=32768`, which the subscription tier rejects; 32768 was never the
deployment configuration. Every recovered artifact was scored by the frozen
v1.2.1 scorers listed in `scorer_hashes.json`.

## Dates

| event | date |
|---|---|
| canonical v1.2 run | 2026-08-04 |
| `mg_basic_003` preserved output | 2026-06-29 |
| three regenerated records | 2026-08-28 |

## Required disclosure

Three of the four records are **regenerations, not recoveries of the original
responses**. The original calls were rejected before generation, so no original
response ever existed to recover. Prompt, input files, scorer and request
configuration are identical to the canonical run; only the wall-clock date differs.

The provider is not deterministic at `temperature = 0`, because the length of the
internal reasoning trace varies between calls. A rerun is therefore a fresh draw
rather than a reproduction. `mg_runcard_004` required two attempts: the first
returned `finish_reason = "length"` with null content. The retained response is the
first usable draw, which follows existing release practice, since 5 of the 27
retained Sarvam outputs already came from a documented retry fill.

A reviewer may reasonably prefer the `S2` exclusion on the grounds that a
regenerated record is not the same evidentiary object as a preserved one. `S1R` is
defensible only if this mixing of run dates is stated plainly in the manuscript.

Provider `reasoning_content` and raw HTTP bodies are deliberately excluded from
this package.
