# Task: Extract Structured Workflow Settings for MadGraph, Pythia8, and Delphes

Extract the workflow configuration for inclusive top-pair production

```text
p p > t t~
```

in the Standard Model at a total proton-proton center-of-mass energy of 13 TeV.

Use these workflow settings:

- output directory: `TTbar_P8_Delphes`;
- number of events: 10000;
- random seed: 42;
- beam energy per proton beam: 6500 GeV;
- Pythia8 showering enabled;
- Delphes detector simulation enabled;
- MadSpin disabled.

Return only one JSON object with this schema. The schema below gives field names and types only; fill the values from the task statement above.

```json
{
  "model": "<string>",
  "initial_state": ["<particle>", "<particle>"],
  "final_state": ["<particle>", "<particle>"],
  "beam_energy_gev": "<number>",
  "output_dir": "<string>",
  "nevents": "<integer>",
  "iseed": "<integer>",
  "shower": "<string>",
  "detector": "<string>",
  "madspin": "<string>"
}
```

Do not include explanations or markdown fences.
