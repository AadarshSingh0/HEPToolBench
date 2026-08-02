# Task: Diagnose a Failed MadGraph Run

Read the provided MadGraph-style failed run log and extract the failure diagnosis.

Return only one JSON object with this schema. The schema below gives field names and types only; extract the values from the provided log and diagnostic message.

```json
{
  "status": "<string>",
  "process": "<string>",
  "error_type": "<string>",
  "offending_line": "<string>",
  "expected_line": "<string>",
  "fix": "<string>"
}
```

Rules:

- Preserve the offending line exactly as it appears in the log.
- Use the expected line shown by the diagnostic message in the log.
- Do not include explanations or markdown fences.
