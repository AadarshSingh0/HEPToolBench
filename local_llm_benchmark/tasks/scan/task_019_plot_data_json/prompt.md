Read `completed_scan_with_benchmark.txt` and return only a JSON object that prepares plot-ready data for the scan.

Required JSON schema. The schema below gives field names and types only; compute values from the completed scan table and plot requirements.

```json
{
  "status": "<string>",
  "scan_parameter": "<string>",
  "x_label": "<string>",
  "y_label": "<string>",
  "x_values_gev": ["<number>"],
  "y_values_pb": ["<number>"],
  "yerr_values_pb": ["<number>"],
  "number_of_plot_points": "<integer>",
  "log_y": "<boolean>",
  "benchmark_marker": {
    "mass_gev": "<number>",
    "cross_section_pb": "<number>"
  },
  "safe_to_plot": "<boolean>"
}
```

Use only successful scan points. Do not include explanations or markdown fences.
