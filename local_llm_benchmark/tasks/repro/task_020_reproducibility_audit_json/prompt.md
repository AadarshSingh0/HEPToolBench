Read `analysis_package_manifest.txt` and return only a JSON reproducibility audit.

Required JSON schema. The schema below gives field names and types only; infer the values from the package manifest.

```json
{
  "status": "<string>",
  "detector_level_claimed": "<boolean>",
  "missing_required_files": ["<string>"],
  "missing_optional_files": ["<string>"],
  "affected_scan_points_gev": ["<number>"],
  "can_reproduce_parton_level_scan": "<boolean>",
  "safe_for_paper_archive": "<boolean>",
  "recommended_action": "<string>"
}
```

Important: Pythia8 and Delphes cards are optional here because detector-level results are not claimed. Do not include explanations or markdown fences.
