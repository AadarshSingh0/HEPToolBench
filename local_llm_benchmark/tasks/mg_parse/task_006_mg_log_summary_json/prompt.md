# Task: Extract a MadGraph Run Summary

Read the provided MadGraph-style run summary log and extract the numerical result.

Return only one JSON object with this schema. The schema below gives field names and types only; extract the values from the provided log.

```json
{
  "status": "<string>",
  "process": "<string>",
  "cross_section_pb": "<number>",
  "cross_section_uncertainty_pb": "<number>",
  "nevents": "<integer>",
  "event_file": "<string>"
}
```

Rules:

- Use picobarns for the cross section and uncertainty.
- Preserve the event file path exactly as written in the log.
- Do not include explanations or markdown fences.
