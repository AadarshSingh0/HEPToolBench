# Ollama HTTP transport

HEPToolBench evaluates Ollama-served models through Ollama's HTTP
`/api/generate` endpoint with non-streaming responses.

Model generations are not captured from the interactive `ollama run` CLI.

## Request model

A benchmark request contains the selected model, prompt, and explicit
HEPToolBench serving options.

The default benchmark context setting is:

```text
num_ctx = 4096
```

The following optional generation controls are also supported:

- `think`
- `temperature`
- `seed`
- `num_predict`

For these optional controls, `auto` means that HEPToolBench does not send an
override and therefore leaves the corresponding Ollama/model default in use.

The top-level launcher exposes these settings through:

```text
--num-ctx
--think
--temperature
--seed
--num-predict
```

## Recorded provenance

The selected run-level serving configuration is recorded in
`run_manifest.json` under `ollama_generation_settings`.

Each model attempt also records HTTP request/response metadata in
`ollama_http_metadata.json`, including information used for reproducibility
and integrity checks.

## Integrity safeguards

The HTTP evaluation path includes safeguards for:

- control-character contamination;
- incomplete or length-terminated generation;
- model-digest changes during resume;
- duplicate or missing evaluations;
- timeout and runner failures;
- run-completeness verification.

Runs that complete the required integrity checks can be marked
`completed_verified`.

## Testing

The transport and generation-setting code is covered by offline unit tests.
The tests use mocked/local interfaces and do not require benchmark model
generations.

From the repository root:

```bash
cd local_llm_benchmark
python3 -m unittest discover -s tests -p 'test_*.py'
```

For normal benchmark usage, see `RUN_LOCAL_MODELS.md`.
