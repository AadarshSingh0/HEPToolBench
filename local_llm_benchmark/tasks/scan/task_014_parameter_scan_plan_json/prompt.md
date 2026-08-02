Read the physics scan request and return only a JSON scan plan.

The JSON must contain these fields:

```json
{
  "status": "<valid|invalid>",
  "process": "<MadGraph process string>",
  "scan_parameter": "<parameter name>",
  "scan_values_gev": ["<number>"],
  "start_gev": "<number>",
  "stop_gev": "<number>",
  "step_gev": "<number>",
  "inclusive_endpoints": "<boolean>",
  "number_of_points": "<integer>",
  "fixed_parameters": {
    "<parameter_name>": "<number>"
  },
  "beam_energy_gev": "<number>",
  "nevents": "<integer>",
  "files_to_modify": ["<string>"],
  "per_point_actions": ["<string>"],
  "outputs_to_collect": ["<string>"],
  "recommended_action": "<string>"
}
```

Use beam energy per beam, not total center-of-mass energy. For a 13 TeV pp collider, the beam energy is 6500 GeV per beam.

Return only JSON. Do not include explanations.
