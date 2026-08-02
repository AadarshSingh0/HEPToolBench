# Task: Extract Structured MadGraph Run-Card Settings

Extract the run-card configuration for a MadGraph Drell-Yan run

```text
p p > e+ e-
```

at a total proton-proton center-of-mass energy of 13 TeV.

Use these run settings:

- number of events: 10000;
- random seed: 42;
- beam energy 1: 6500 GeV;
- beam energy 2: 6500 GeV;
- minimum charged-lepton transverse momentum: 20 GeV;
- maximum charged-lepton pseudorapidity: 2.5.

Return only one JSON object with this schema. The schema below gives field names and types only; fill the values from the task statement above.

```json
{
  "nevents": "<integer>",
  "iseed": "<integer>",
  "ebeam1_gev": "<number>",
  "ebeam2_gev": "<number>",
  "ptl_min_gev": "<number>",
  "eta_l_max": "<number>"
}
```

Do not include explanations or markdown fences.
