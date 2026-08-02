# Task: Validate a Pythia8 Configuration

Read the requested Pythia8 setup and the provided `.cmnd` configuration.

The requested setup is:

- generate 10000 events
- use a fixed random seed of 42
- enable initial-state radiation
- enable final-state radiation
- enable multiparton interactions
- enable hadronization
- write HepMC output

Return only one JSON object with this schema. The schema below gives field names and types only; infer the values by checking the provided configuration.

```json
{
  "status": "<string>",
  "number_of_events": "<integer>",
  "seed_fixed": "<boolean>",
  "seed_value": "<integer>",
  "isr_enabled": "<boolean>",
  "fsr_enabled": "<boolean>",
  "mpi_enabled": "<boolean>",
  "hadronization_enabled": "<boolean>",
  "hepmc_output_enabled": "<boolean>",
  "missing_or_wrong_settings": ["<string>"],
  "failure_stage": "<string>",
  "recommended_fix": "<string>"
}
```

Rules:

- Use `status: "valid"` only if every requested setting is satisfied.
- Use `status: "invalid"` if any requested setting is missing or has the wrong value.
- Preserve the exact setting name in `missing_or_wrong_settings`.
- Do not include explanations or markdown fences.
