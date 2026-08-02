# Task: Drell-Yan Structured JSON Extraction

Extract the physics intent for a MadGraph run as JSON.

The desired process is Standard Model Drell-Yan production

```text
p p > e+ e-
```

for proton-proton collisions at a total center-of-mass energy of 13 TeV.

MadGraph uses beam energies, so 13 TeV proton-proton collisions correspond to 6500 GeV per beam.

Use `DY_ee` as the output directory and 10000 generated events.

Return only one JSON object. Do not write a MadGraph card. Do not include explanations.

Required JSON schema. The schema below gives field names and types only; fill the values from the task statement above.

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
