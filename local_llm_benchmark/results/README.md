# Results directory

- `local_r01/raw/`: per-task JSON and CSV outputs from the 17-model run.
- `local_r01/compiled/`: consolidated first-run tables and runtime summaries.
- `local_r02/`: second complete run of the six-model shortlist.
- `local_r03/`: third complete run of the six-model shortlist.
- `repeat_analysis/`: combined three-repeat summaries.

A semantic failure, including a score of zero, is a valid benchmark result.
Infrastructure failures and missing generations are tracked separately and
must not be interpreted as model failures.
