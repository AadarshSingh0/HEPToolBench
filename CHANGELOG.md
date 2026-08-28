# Changelog

## [1.2.1] - candidate (2026-08-28)

- Apply prompt-faithful scoring to `mg_basic_002` and `mg_workflow_005`.
- Preserve the dependent `mg_debug_002` historical output-name behavior.
- Retain all 42 deployments after recovering four Sarvam-105B calls that had
  previously failed with provider HTTP 400 before model output.
- Add the balanced 42 x 31 corrected canonical dataset, corrected stability
  results, change ledgers, Paper A correction assets, provenance, and validation.
- Document that three Sarvam records are fresh draws from 2026-08-28 and one is
  a preserved 2026-06-29 output; prompts, configuration, and scorers are
  identical, but temperature-zero provider generation is nondeterministic.
- Preserve v1.2 and its tag unchanged for historical reproducibility.

No benchmark model or HEP application was rerun.
