Given the cutflow table below, return only a JSON object that diagnoses the analysis cutflow.

Use the following definitions exactly:
- The dominant signal-loss cut is the cut with the largest relative signal loss between consecutive rows.
- Step efficiency is current_signal_events / previous_signal_events.
- Relative signal loss is 1 - step_efficiency.
- The final selection is statistically usable only if the final signal yield is at least 100 events.
- Report s_over_sqrt_b using the final signal and background yields, rounded to two decimal places.

Return exactly these fields. The schema below gives field names and types only; compute the values from the cutflow table.

```json
{
  "status": "<string>",
  "final_signal_events": "<integer>",
  "final_background_events": "<integer>",
  "dominant_signal_loss_cut": "<string>",
  "dominant_signal_loss_step_efficiency": "<number>",
  "dominant_signal_loss_fraction": "<number>",
  "s_over_sqrt_b": "<number>",
  "statistically_usable": "<boolean>",
  "recommended_action": "<string>"
}
```
