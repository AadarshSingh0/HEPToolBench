# Results directory

This directory contains selected, curated result artifacts distributed with
HEPToolBench for reproducibility.

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

Historical host paths and private-network addresses inside frozen provenance
records describe the original execution environment; they are not public
service endpoints.

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
