Read the scan-point request and the SLHA-like `param_card.dat` excerpt.

Return only a JSON object describing the patch that should be applied to `param_card.dat`.
Do not return the full card. Do not include explanations.

Required JSON schema. The schema below gives field names and types only; infer values from the scan-point request and the card excerpt.

```json
{
  "status": "<string>",
  "file_to_modify": "<string>",
  "scan_point_label": "<string>",
  "updates": [
    {
      "block": "<string>",
      "identifier": "<string>",
      "parameter": "<string>",
      "old_value": "<number>",
      "new_value": "<number>",
      "unit": "<string or null>"
    }
  ],
  "unchanged": [
    {
      "block": "<string>",
      "identifier": "<string>",
      "parameter": "<string>",
      "value": "<number>",
      "reason": "<string>"
    }
  ]
}
```

Important:
- Change `mS` in `BLOCK MASS` for PDG code `9000001`.
- Change `gS` in `BLOCK COUPLINGS` entry `1`.
- Do not modify the `DECAY 9000001` width.
