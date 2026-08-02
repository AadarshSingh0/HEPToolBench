# Task: Extract a MadGraph Run Summary With Unit Conversion

Read the provided MadGraph-style run summary log and extract the numerical result.

The log reports the cross section and uncertainty in femtobarns. Return the cross section and uncertainty in picobarns.

Use:

```text
1000 fb = 1 pb
```

Return only one JSON object with this schema. The schema below gives field names and types only; extract values from the log and perform the unit conversion.

```json
{
  "status": "<string>",
  "process": "<string>",
  "cross_section_pb": "<number>",
  "cross_section_uncertainty_pb": "<number>",
  "input_unit": "<string>",
  "output_unit": "<string>",
  "nevents": "<integer>",
  "event_file": "<string>"
}
```

Rules:

- Convert femtobarns to picobarns.
- Preserve the event file path exactly as written in the log.
- Do not include explanations or markdown fences.
