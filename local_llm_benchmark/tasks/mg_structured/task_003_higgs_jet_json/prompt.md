# Task: Extract Structured MadGraph Parameters for Higgs Plus Jet Production

Extract the physics intent for a MadGraph run.

The desired process is Standard Model Higgs plus jet production:

```text
p p > h j
```

at a total proton-proton center-of-mass energy of 13 TeV.

MadGraph uses beam energies, so use 6500 GeV per beam.

Use `HJ` as the output directory and 10000 events.

Return only one JSON object with this schema. The schema below gives field names and types only; fill the values from the task statement above.

```json
{
  "model": "<string>",
  "initial_state": ["<particle>", "<particle>"],
  "final_state": ["<particle>", "<particle>"],
  "beam_energy_gev": "<number>",
  "output_dir": "<string>",
  "nevents": "<integer>"
}
```

Do not include explanations or markdown fences.
