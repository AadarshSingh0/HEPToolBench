# Task: Structured repair patch for a broken top-pair MadGraph card

STRUCTURED DEBUGGING REQUIREMENTS:
- `corrected_lines` must contain the complete minimal repair patch, not only the line you think is most important.
- If the broken input contains an invalid or missing process command, include the corrected `generate ...` line.
- If the broken input contains invalid beam commands or missing beam-energy settings, include corrected `set ebeam1 ...` and `set ebeam2 ...` lines.
- If the output directory is wrong or missing, include the corrected `output ...` line.
- The `reason` field must be one single-line JSON string. Do not put a literal line break inside any JSON string.

CRITICAL OUTPUT RULES:
- Return exactly one raw JSON object.
- Do not use Markdown.
- Do not wrap the answer in ```json or any code fence.
- Do not add explanation before or after the JSON.
- The first character of your response must be { and the last character must be }.
- Use double quotes for all JSON strings.
- Do not include comments inside the JSON.


You are given a broken MadGraph `proc_card.dat` as an input file.

Target physics request:

- inclusive Standard Model top-pair production, p p -> t t~, at 13 TeV proton-proton center-of-mass energy.
- Use the output directory `TTbar`.
- Diagnose the broken card and return a minimal structured repair patch.

Return only a JSON object named conceptually as `repair.json`. Do not include Markdown fences, prose outside JSON, or chain-of-thought.

Use this de-leaked schema. It gives only keys and types; it does not contain the answer values:

```json
{
  "error_type": "<short label for the main error class>",
  "faulty_lines": ["<line copied from the broken input card>", "<another faulty line if relevant>"],
  "corrected_lines": ["<corrected MadGraph line>", "<another corrected line if relevant>"],
  "output_dir": "<output directory name>",
  "reason": "<one short sentence explaining the repair>"
}
```

Important requirements:

- Give a repair patch, not a long explanation.
- Use `generate` for the process line.
- Use MadGraph syntax with `>` rather than arrow notation.
- Use valid MadGraph beam-energy commands for 6500 GeV per beam.
- Do not use `beam1` or `beam2` as commands.
- Do not put placeholder strings in your final answer.

Additional hint about this task class: MadGraph anti-top syntax is t~, not tbar.