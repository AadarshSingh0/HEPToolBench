Read the final scan table and return a benchmark recommendation as JSON.

The JSON must contain these fields:

```json
{
  "status": "<string>",
  "scan_parameter": "<string>",
  "safe_to_make_final_plot": "<boolean>",
  "total_points": "<integer>",
  "successful_points": "<integer>",
  "failed_points": "<integer>",
  "missing_points": "<integer>",
  "usable_masses_gev": ["<number>"],
  "benchmark_mass_gev": "<number>",
  "benchmark_cross_section_pb": "<number>",
  "selection_rule": "<string>",
  "monotonic_decreasing_cross_section": "<boolean>",
  "next_action": "<string>"
}
```

Definitions:
- `status` should summarize whether the scan is complete.
- `safe_to_make_final_plot` is true only if every intended scan point succeeded.
- `usable_masses_gev` should list all successful mass points.
- The benchmark mass must follow the benchmark-selection rule written in the input file.
- `monotonic_decreasing_cross_section` refers to the successful scan points ordered by increasing mass.

Return only JSON. Do not include explanations or markdown fences.
