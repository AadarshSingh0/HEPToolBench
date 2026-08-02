Read the LHE file scan report and return only a JSON object that validates whether the generated event file is usable for the requested run.

Required JSON keys:
- status: "valid" or "incomplete"
- process: process found in the LHE header
- process_correct: true or false
- event_file: path to the LHE file
- file_present: true or false
- requested_events: requested event count
- observed_events: number of events scanned in the LHE file
- event_count_matches: true or false
- missing_events: requested_events minus observed_events
- cross_section_pb: cross section in pb
- cross_section_uncertainty_pb: uncertainty in pb
- negative_weight_events: number of negative-weight events
- negative_weight_fraction: fraction of negative-weight events
- failure_stage: use "none" if valid, otherwise use "event_count_validation"
- recommended_action: one short sentence explaining what to do

The requested process is p p > h j and the requested event count is 10000.
Return only JSON. Do not include markdown or explanation.
