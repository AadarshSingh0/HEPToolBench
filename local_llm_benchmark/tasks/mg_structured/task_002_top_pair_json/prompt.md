# Task: Top-Pair Structured JSON Extraction

Extract the physics intent for a MadGraph run as JSON.

The desired process is inclusive top-pair production

```text
p p > t t~
```

in the Standard Model at a total proton-proton center-of-mass energy of 13 TeV.

MadGraph uses beam energies, so 13 TeV proton-proton collisions correspond to 6500 GeV per beam.

Use `TTbar` as the output directory and 10000 generated events.

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
