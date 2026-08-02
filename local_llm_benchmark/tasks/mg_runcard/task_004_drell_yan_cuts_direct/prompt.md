# Task: MadGraph Run Card Settings for Drell-Yan With Cuts

Write the relevant MadGraph `run_card.dat` assignment lines for a Drell-Yan run

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

Return only the six relevant `run_card.dat` assignment lines. Use MadGraph run-card syntax of the form:

```text
value = parameter
```

Do not write a process card. Do not use `set` commands. Do not include explanations.
