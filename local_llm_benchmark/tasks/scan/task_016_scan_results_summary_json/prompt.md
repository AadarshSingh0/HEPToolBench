Read the scan result table and return only a JSON summary.

Required JSON schema. The schema below gives field names and types only; compute values from the scan result table.

```json
{
  "status": "<string>",
  "scan_parameter": "<string>",
  "total_points": "<integer>",
  "successful_points": "<integer>",
  "failed_points": "<integer>",
  "failed_masses_gev": ["<number>"],
  "failed_run_directories": ["<string>"],
  "max_cross_section_mass_gev": "<number>",
  "max_cross_section_pb": "<number>",
  "min_successful_cross_section_mass_gev": "<number>",
  "min_successful_cross_section_pb": "<number>",
  "monotonic_decreasing_successful_points": "<boolean>",
  "rerun_required": "<boolean>",
  "recommended_action": "<string>"
}
```

Rules:
- Ignore failed points when finding the maximum/minimum successful cross section.
- Do not interpolate missing or failed cross sections.
- The scan is incomplete if any requested point failed.
- The successful cross sections are monotonic decreasing if they decrease as mS increases when failed points are skipped.
