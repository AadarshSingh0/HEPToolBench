# Results directory

This directory contains selected, curated result artifacts distributed with
HEPToolBench for reproducibility.

## HEPToolBench v1.2.1 correction candidate (B1_W1_S1R)

[`heptoolbench_v1_2_1_correction/`](heptoolbench_v1_2_1_correction/) contains the
42-deployment x 31-task corrected dataset (1,302 records), prompt-faithful
scorer corrections for `mg_basic_002` and `mg_workflow_005`, recovered Sarvam
outputs with complete provenance, corrected Paper A assets, and validation
evidence. Three Sarvam records are regenerated and one is a preserved output;
the prompts, configuration, and scorers are identical, with a documented
temperature-zero nondeterminism caveat. The candidate supersedes the earlier
41 x 31 S2 candidate; v1.2 remains below for historical reproducibility.

## HEPToolBench v1.2 consolidated result snapshot

The consolidated result dataset is:

- `heptoolbench_v1_2_42deployments_31tasks_20260804.csv`

It contains one final scored record for every deployment--task pair:
42 deployments across 31 tasks, giving 1302 evaluations. The dataset
includes scores, pass/fail labels, runtime configurations, failure modes,
and provenance metadata. Machine-specific paths and private Ollama host
addresses were replaced with public placeholders. Scientific scoring and
evaluation fields were not changed.

## Canonical local native-interface responses

[`heptoolbench_v1_2_local_native_responses/`](heptoolbench_v1_2_local_native_responses/)
contains the 240 canonical raw outputs from 30 locally served deployments on
eight native-interface tasks. It includes each task's exact model-facing
prompt, scores, pass labels, failure modes, provenance, and checksums. A
separately labelled 100-generation Qwen2.5-Coder 7B experiment is included for
self-contained review but is not part of the 240-response benchmark set. API
outputs are excluded.

## HTTP-clean stability dataset

The canonical stability dataset is:

- `stability_httpclean_modern_final_10models_1550rows.csv`
- `stability_httpclean_modern_final_run_index.csv`
- `stability_httpclean_modern_final_audit.json`

It contains 10 model deployments evaluated on all 31 HEPToolBench v1.2 tasks
with five repeats per task:

10 models x 31 tasks x 5 repeats = 1550 evaluations.

These runs use the Ollama HTTP `/api/generate` transport with non-streaming
responses. Older subprocess-based local stability cohorts are not included in
the public stability dataset.

For Gemma4 26B, 23 generations reached the configured `num_ctx=4096` context
limit and ended with Ollama `done_reason="length"`. These are retained as
scored model outputs rather than treated as transport or infrastructure
failures.

## Freeform ttbar experiment

`freeform_ttbar_qwen2_5_coder_7b_100/` contains the preserved 100-generation
freeform ttbar syntax experiment used for qualitative error analysis.

The raw model generations and scientific classification data are retained.
Machine-specific provenance fields in the public copy are normalized as
described below.

## Generated runs

New benchmark executions are generated locally and are not intended to be
committed to this repository. Runtime results should remain in their generated
run directories unless intentionally curated for a release.

## Public-release provenance normalization

Machine-specific filesystem roots and private network addresses in retained
historical result metadata were normalized for the public repository.
Repository paths are stored relative to the benchmark root where possible,
and the original private Ollama address is represented as
`http://PRIVATE_OLLAMA_HOST:11434`.

This normalization changes provenance-only metadata. Model responses, task
IDs, scores, pass/fail values, failure modes, timestamps, and stability
statistics are unchanged.
