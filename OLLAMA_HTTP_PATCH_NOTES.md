# HEPToolBench Ollama HTTP transport patch

This patch replaces generated-output capture through the interactive
`ollama run` CLI with Ollama's non-streaming HTTP endpoint:

```text
POST /api/generate
stream: false
options.num_ctx: 4096
```

The administrative `ollama pull` command remains available in
`run_benchmark.py`; it does not capture or score model output.

## Scientific safeguards

- Rejects C0, DEL, and C1 control characters before an artifact is written or
  scored.
- Records HTTP-generation metadata, prompt hashes, output hashes, explicit
  context size, completion reason, token counts, and model digest.
- Pins model digests in the run manifest and refuses a resume if a digest
  changed.
- Refuses to resume legacy pre-patch runs.
- Uses `model -> repeat -> task` order, so each repeat is a complete task round.
- Stops immediately on infrastructure-invalid responses.
- Runs a final completeness, duplication, contamination, timeout, truncation,
  runner-error, and digest audit.
- Marks a usable completed run as `completed_verified`.

## Offline tests

From the repository root:

```bash
python3 -m unittest -v \
  local_llm_benchmark/tests/test_ollama_http_runner.py
```

The tests use a local mock HTTP server and make no model calls. They verify:

1. clean non-streaming output and metadata;
2. rejection of injected `ESC[5D` contamination before artifact creation;
3. truncation detection;
4. a passing integrity audit for a complete clean run;
5. integrity-audit failure for a contaminated artifact; and
6. rejection of a changed model digest.
