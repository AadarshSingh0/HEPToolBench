#!/usr/bin/env python3
"""Export the exact tabular sources consumed by the v1.2.1 Paper A figures."""

from __future__ import annotations

import numpy as np
import pandas as pd

from build import DISPLAY, PAIRS, ROOT, leaderboard, load, primary

FREEFORM = [
    "mg_basic_001", "mg_basic_002", "mg_basic_003", "mg_debug_001",
    "mg_debug_002", "mg_debug_003", "mg_runcard_004", "mg_workflow_005",
]
OUT = ROOT / "figure_data"
OUT.mkdir(parents=True, exist_ok=True)

data = load()
lb = leaderboard(data)
lb.to_csv(OUT / "fig1_leaderboard.csv", index=False)

main = primary(data)
pairs = []
for model, group in main.groupby("model"):
    native = group[group.task_id.isin([pair[0] for pair in PAIRS])]
    structured = group[group.task_id.isin([pair[1] for pair in PAIRS])]
    if len(native) == 5 and len(structured) == 5:
        pairs.append({
            "model": model,
            "display": DISPLAY.get(model, model),
            "native_mean": native.score.mean(),
            "structured_mean": structured.score.mean(),
            "native_passes": int(native.passed.sum()),
            "structured_passes": int(structured.passed.sum()),
            "gain": structured.score.mean() - native.score.mean(),
        })
pd.DataFrame(pairs).sort_values("native_mean").to_csv(OUT / "fig2_matched_pairs.csv", index=False)

lb[lb.total_b.notna()].to_csv(OUT / "fig3_scale.csv", index=False)

debug = primary(data, "structured_debug3")
structured_ids = sorted(set(main.task_id) - set(FREEFORM))
structured = (
    main[main.task_id.isin(structured_ids)]
    .groupby("model", as_index=False)
    .agg(structured_mean=("score", "mean"), structured_passes=("passed", "sum"))
)
debug_by_model = (
    debug.groupby("model", as_index=False)
    .agg(debug_mean=("score", "mean"), debug_passes=("passed", "sum"))
)
lb.merge(structured, on="model").merge(debug_by_model, on="model").to_csv(
    OUT / "fig4_structured_debug.csv", index=False
)

stability = pd.read_csv(ROOT / "data/HEPToolBench_stability_v1_2_1_10models_x5.csv")
stability["passed"] = stability["passed"].astype(str).str.lower().eq("true")
stability = stability[stability.task_partition == "main28"]
repeat_rows = (
    stability.groupby(["model", "repeat"], as_index=False)
    .agg(mean_score=("score", "mean"), passes=("passed", "sum"), tasks=("task_id", "nunique"))
)
canonical = lb.set_index("model")
repeat_rows["display"] = repeat_rows.model.map(lambda model: DISPLAY.get(model, model))
repeat_rows["canonical_mean"] = repeat_rows.model.map(canonical.mean_score)
repeat_rows["canonical_passes"] = repeat_rows.model.map(canonical.passes)
repeat_rows.to_csv(OUT / "fig5_stability_repeats.csv", index=False)

print("wrote", len(list(OUT.glob("*.csv"))), "figure-source CSV files")
