# Task: Validate a Delphes Object Summary

Read the requested detector-level selection and the provided Delphes-style object summary.

The requested analysis selection is:

- exactly 1 isolated charged lepton, where the lepton may be an electron or muon
- at least 4 reconstructed jets
- at least 2 b-tagged jets
- missing transverse energy greater than 30 GeV

Return only one JSON object with this schema. The schema below gives field names and types only; infer the values from the provided object summary.

```json
{
  "status": "<string>",
  "selected_leptons": "<integer>",
  "electron_count": "<integer>",
  "muon_count": "<integer>",
  "jet_count": "<integer>",
  "b_tagged_jet_count": "<integer>",
  "missing_et_gev": "<number>",
  "lepton_requirement_passed": "<boolean>",
  "jet_requirement_passed": "<boolean>",
  "b_tag_requirement_passed": "<boolean>",
  "met_requirement_passed": "<boolean>",
  "missing_or_failed_requirements": ["<string>"],
  "failure_stage": "<string>",
  "recommended_action": "<string>"
}
```

Rules:

- Use `status: "valid"` only if all requested object requirements pass.
- Use `status: "invalid"` if at least one requested object requirement fails.
- `selected_leptons` is the sum of isolated selected electrons and isolated selected muons.
- Do not include explanations or markdown fences.
