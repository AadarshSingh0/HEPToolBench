# HEPToolBench v1.2 suite scope

HEPToolBench v1.2 contains 31 frozen benchmark tasks.

## Main suite

The main benchmark suite contains 28 tasks covering HEP software workflow
generation, structured artifacts, debugging, parsing, validation, scan
planning, result interpretation, plotting, and reproducibility checks.

The launcher refers to this subset as:

```text
main28
```

## Structured-debug extension

Three additional structured-debug tasks extend the suite:

- `mg_debug_structured_001`
- `mg_debug_structured_002`
- `mg_debug_structured_003`

Together, the 28 main tasks and 3 extension tasks form:

```text
full31
```

## Reporting results

Results obtained on `main28` and `full31` are not directly interchangeable.
Published benchmark results should state explicitly which suite was used.

When comparing deployments, the task set, repeat count, model identity,
serving configuration, and benchmark version should be reported.

For Ollama evaluations, non-default context, reasoning, temperature, seed,
or generation-budget settings should also be reported because these settings
can affect benchmark behavior.
