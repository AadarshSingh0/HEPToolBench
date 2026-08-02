Read the intended scan grid and the scan job-output manifest.

Return only a JSON object named as the content of `recovery_plan.json`.
Do not include markdown fences or explanations.

The JSON object must contain these fields:

```json
{
  "status": "<string>",
  "scan_parameter": "<string>",
  "total_intended_points": "<integer>",
  "completed_points_gev": ["<number>"],
  "failed_points_gev": ["<number>"],
  "missing_points_gev": ["<number>"],
  "points_to_rerun_gev": ["<number>"],
  "number_of_reruns": "<integer>",
  "rerun_run_directories": ["<string>"],
  "safe_to_make_final_plot": "<boolean>",
  "recommended_action": "<string>"
}
```

Definitions:

- A completed point has `job_status = success` and has both `cross_section.txt` and `events.lhe.gz`.
- A failed point has `job_status = failed`.
- A missing point has `job_status = missing_directory` or an absent run directory.
- `points_to_rerun_gev` must include both failed and missing points, but not completed points.
- `number_of_reruns` is the number of points in `points_to_rerun_gev`.
- `safe_to_make_final_plot` is true only if every intended scan point is completed successfully.
