# Task: Validate a MadGraph/Pythia/Delphes Run Output

Read the provided run manifest and decide whether the requested workflow produced all expected outputs.

The workflow requested:

- MadGraph hard-process event generation
- Pythia8 showering
- Delphes detector simulation

Return only one JSON object with this schema. The schema below gives field names and types only; infer the values from the manifest.

```json
{
  "status": "<string>",
  "process": "<string>",
  "requested_events": "<integer>",
  "lhe_present": "<boolean>",
  "lhe_events": "<integer>",
  "pythia8_requested": "<boolean>",
  "pythia8_present": "<boolean>",
  "pythia8_events": "<integer>",
  "delphes_requested": "<boolean>",
  "delphes_present": "<boolean>",
  "missing_outputs": ["<string>"],
  "event_count_consistent": "<boolean>",
  "failure_stage": "<string>",
  "recommended_action": "<string>"
}
```

Rules:

- Use `status: "success"` only if all requested stages produced their expected outputs.
- Use `status: "incomplete"` if an earlier stage succeeded but a requested later-stage output is missing.
- Preserve any missing file path exactly as written in the manifest.
- `event_count_consistent` should be true if all present event files have the requested number of events.
- Do not include explanations or markdown fences.
