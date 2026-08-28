# HEPToolBench v1.2.1 candidate — policy `B1_W1_S1R` (42 x 31)

**Status: review candidate. Nothing here is committed or pushed.**
Built 2026-08-28 from the authoritative 42x31 correction package, the approved
B1_W1 scorer changes, and documented Sarvam-105B recovery evidence.

## What this changes relative to the approved candidate

`B1` and `W1` are unchanged — the two approved scorer corrections are applied
exactly as before, from the same frozen scorers:

| scorer | sha256 |
|---|---|
| `mg_basic_002` | `8791cffedbd731a61fab45cf46245485dc52b7a9fe7bfbd3807a5c60577c9a4f` |
| `mg_workflow_005` | `48a59d295e5728db6589cbb8edcaf6689602d9609ffa28fc1fa88d8894fafe3c` |

Only the Sarvam policy changes. `S2` excluded all 31 Sarvam-105B rows because
four records were provider HTTP-400 failures that returned no model output.
**All four now have model output**, so the ground for exclusion is gone.
`S1R` = retain the complete deployment with recovered output.

| task | v1.2 | v1.2.1 S1R | origin |
|---|---:|---:|---|
| `benchmark_recommendation_018` | 0.0 error | **0.95 PASS** | regenerated 2026-08-28 |
| `mg_runcard_004` | 0.0 error | 0.720 fail | regenerated 2026-08-28 |
| `mg_basic_002` | 0.0 error | 0.075 fail | regenerated 2026-08-28 |
| `mg_basic_003` | 0.0 error | 0.075 fail | preserved 2026-06-29 output |
| `mg_workflow_005` | 0.42 fail | 0.460 fail | preserved v1.2 output, W1 rescore |

All three regenerated records used the validated request configuration
(`max_tokens=4096`, `temperature=0`, `reasoning_effort="low"`) — the configuration
the request-configuration audit identified as the one that produced the 27 retained
outputs. Reasoning was not disabled and the token cap was not raised. Every
recovered artifact was scored in this build by the live B1/W1 scorers.

## Headline result

Matched native/structured pairs, 5 pairs x 42 deployments = 210 cases:

**mean 0.418 -> 0.902**, strict passes **21/210 -> 159/210**,
41 of 42 deployments improve, Wilcoxon W = 897, p = 3.2e-12.

This was obtained independently, after B1/W1 rescoring, from the rebuilt cohort.
It is **not** the 0.402 figure produced by patching v1.2 with the recovered scores
alone, and it is not the released 0.398. Do not cite 0.402.

Two consistency checks that fall out of the rebuild:
* Structured passes are 159/210 here and 159/210 in released v1.2 — B1/W1 touch
  only native tasks, so the structured side must be unchanged, and it is.
* Native passes 17/210 (v1.2) -> 21/210. All four added passes come from B1;
  Sarvam contributes none, because all five of its native artifacts still fail.

## Statistics changed against the approved 41x31 candidate

| statistic | `B1_W1_S2` (41x31) | `B1_W1_S1R` (42x31) |
|---|---:|---:|
| deployments / distinct checkpoints | 41 / 40 | 42 / 41 |
| main-suite observations | 1148 | 1176 |
| matched native mean | 0.419 | 0.418 |
| matched structured mean | 0.901 | 0.902 |
| matched native passes | 21/205 | 21/210 |
| matched structured passes | 155/205 | 159/210 |
| deployments improved | 40/41 | 41/42 |
| Wilcoxon W, p | 855, 6.4e-12 | 897, 3.2e-12 |
| size correlation n, rho, p | 33, 0.736, 1.1e-06 | 34, 0.737, 6.8e-07 |
| structured-debug API passes | 28/33 | 30/36 |
| structured-debug API mean | 0.983 | 0.978 |
| debug route Mann-Whitney p | 0.0073 | 0.0101 |
| debug/schema Spearman rho, p | 0.762, 7.4e-09 | 0.742, 1.9e-08 |

Unchanged: all local structured-debug figures (43/90, mean 0.832), every
size-class native/structured mean except `large`, and the entire stability
analysis — Sarvam-105B is not among the 10 repeat models, so
`HEPToolBench_stability_v1_2_1_10models_x5.csv` is carried over untouched.

Sarvam-105B enters the leaderboard at 12/28 passes, mean 0.784.

## Required disclosure

Three of the four recovered records are **regenerations, not recoveries of the
original responses**. The original calls were rejected before generation, so no
original response ever existed. Two dates are involved — 2026-08-28 for three
records and 2026-06-29 for `mg_basic_003` — against a canonical run of 2026-08-04.
Prompt, input files, scorer and request configuration are identical in every case;
only the wall-clock date differs. The provider is not deterministic at
`temperature=0` because the reasoning-trace length varies, so a rerun is a fresh
draw rather than a reproduction. `mg_runcard_004` needed two attempts: the first
returned `finish_reason="length"` with null content.

A reviewer may reasonably prefer `S2` on the grounds that a regenerated record is
not the same evidentiary object as a preserved one. `S1R` is the stronger choice
only if that mixing is disclosed plainly.

## Contents

- `data/` — the 42x31 corrected canonical CSV, and the carried-over stability CSV
- `build_summary.json` — record counts and source/output sha256
- `provenance/sarvam_s1r_change_ledger.csv` — the five changed Sarvam rows
- `provenance/RECOVERY.md`, `recovery_manifest*.json` — recovery evidence
- `paper_a/scripts/` — unmodified pipeline except `DATA_FILE`
- `paper_a/tables/`, `paper_a/figures/`, `paper_a/figure_data/`, `scripts/numbers.json`
