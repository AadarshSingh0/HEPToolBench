# Task: Repair a Higgs Plus Jet MadGraph Card

The input file is an invalid MadGraph process card for Standard Model Higgs plus jet production:

```text
p p > h j
```

at a total proton-proton center-of-mass energy of 13 TeV.

Repair the file so that it becomes a valid `proc_card.dat`.

Requirements:

- use `import model sm`;
- use the proton definition `define p = g u c d s u~ c~ d~ s~`;
- use the jet definition `define j = g u c d s u~ c~ d~ s~`;
- use the MadGraph process line `generate p p > h j`;
- use `HJ` as the output directory;
- use 6500 GeV for each beam.

Return only the repaired `proc_card.dat` content. Do not include explanations.
