# Task: MadGraph Workflow Script With Pythia8 and Delphes

Write a complete MadGraph5 command script for inclusive top-pair production

```text
p p > t t~
```

in the Standard Model at a total proton-proton center-of-mass energy of 13 TeV.

Use these workflow settings:

- output directory: `TTbar_P8_Delphes`;
- number of events: 10000;
- random seed: 42;
- beam energy 1: 6500 GeV;
- beam energy 2: 6500 GeV;
- Pythia8 showering enabled;
- Delphes detector simulation enabled;
- MadSpin disabled.

Use the proton definition:

```text
define p = g u c d s u~ c~ d~ s~
```

Return only the completed MG5 script content. Do not include explanations or markdown fences.
