# HEPToolBench tests

This folder contains offline tests for the current Ollama evaluation path.

## Test files

`test_ollama_http_runner.py`

Tests the non-streaming Ollama HTTP transport and benchmark integrity
behavior with mocked/local interfaces. It does not require a real model run.

`test_ollama_generation_settings.py`

Tests parsing, validation, default behavior, and request construction for
Ollama generation settings.

## Run all tests

From `local_llm_benchmark/`:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

These tests are intended to run without downloading or invoking an Ollama
model.
