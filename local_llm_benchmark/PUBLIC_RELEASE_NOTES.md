# HEPToolBench public release notes

This directory is a curated public copy of the HEPToolBench benchmark,
local-model evaluations, generated artifacts, and repeatability analysis.

## Included evaluation sets

- `local_r01`: 17 local models evaluated on all 28 main-suite tasks.
- `local_r02`: second complete run for the six-model shortlist.
- `local_r03`: third complete run for the six-model shortlist.
- `repeat_analysis`: combined three-repeat quality, stability, and latency
  summaries.

## Main first-run results

- Gemma 4 31B: 20/28 passes, mean score 0.7959.
- Llama 3.3 70B: 19/28 passes, mean score 0.8084.
- Gemma 4 26B: 19/28 passes, mean score 0.7659.
- DeepSeek-R1 70B: 19/28 passes, mean score 0.7391.
- Existing Llama 3 8B baseline: 12/28 passes, mean score 0.6766.

## Three-repeat shortlist

The repeated shortlist contains:

- Gemma 4 31B
- Llama 3.3 70B
- Gemma 4 26B
- Qwen3-Coder-Next Q4_K_M
- Qwen2.5-Coder 14B
- Llama 3 8B

Qwen3-Coder-Next was selected as the principal practical agent candidate
because it provides a strong quality--latency compromise. Llama 3.3 70B is
retained as a slower high-quality fallback, and Llama 3 8B is retained as
the original agent baseline.

## Provenance note

The first local run initially omitted two `.log` benchmark input files due
to an overly broad copy exclusion. The authoritative task directory was
restored and the missing evaluations were rerun. Final result JSON files
and consolidated CSV tables are authoritative. Historical failed execution
logs are not included in this curated public release.

Personal absolute paths have been replaced with `<BENCHMARK_ROOT>` and
`<USER_HOME>` in this public copy.
