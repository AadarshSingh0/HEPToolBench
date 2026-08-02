# Task: Higgs Plus Jet MadGraph Card From Free-Form Instruction

Write a complete MadGraph process card for Standard Model Higgs plus jet production

```text
p p > h j
```

at a total proton-proton center-of-mass energy of 13 TeV.

Use the following multiparticle definitions:

```text
define p = g u c d s u~ c~ d~ s~
define j = g u c d s u~ c~ d~ s~
```

MadGraph uses beam energies, so 13 TeV proton-proton collisions correspond to 6500 GeV per beam.

Use `HJ` as the output directory.

Return only the completed `proc_card.dat` content. Do not include explanations.
