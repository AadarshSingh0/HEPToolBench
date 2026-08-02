#!/usr/bin/env python3
"""Evaluate a single HEPToolBench submission."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

TASK_SCORERS = {
    "mg_basic_001": ROOT / "tasks/mg_basic/task_001_drell_yan_template/tests/score.py",
    "mg_basic_002": ROOT / "tasks/mg_basic/task_002_top_pair_freeform/tests/score.py",
    "mg_basic_003": ROOT / "tasks/mg_basic/task_003_higgs_jet_freeform/tests/score.py",
    "mg_debug_001": ROOT / "tasks/mg_debug/task_001_drell_yan_repair/tests/score.py",
    "mg_debug_002": ROOT / "tasks/mg_debug/task_002_top_pair_repair/tests/score.py",
    "mg_debug_003": ROOT / "tasks/mg_debug/task_003_higgs_jet_repair/tests/score.py",
    "mg_debug_structured_001": ROOT / "tasks/mg_debug_structured/task_001_drell_yan_repair_json/tests/score.py",
    "mg_debug_structured_002": ROOT / "tasks/mg_debug_structured/task_002_top_pair_repair_json/tests/score.py",
    "mg_debug_structured_003": ROOT / "tasks/mg_debug_structured/task_003_higgs_jet_repair_json/tests/score.py",
    "mg_structured_001": ROOT / "tasks/mg_structured/task_001_drell_yan_json/tests/score.py",
    "mg_structured_002": ROOT / "tasks/mg_structured/task_002_top_pair_json/tests/score.py",
    "mg_structured_003": ROOT / "tasks/mg_structured/task_003_higgs_jet_json/tests/score.py",
    "mg_runcard_004": ROOT / "tasks/mg_runcard/task_004_drell_yan_cuts_direct/tests/score.py",
    "mg_runcard_structured_004": ROOT / "tasks/mg_runcard_structured/task_004_drell_yan_cuts_json/tests/score.py",
    "mg_workflow_005": ROOT / "tasks/mg_workflow/task_005_ttbar_pythia_delphes_direct/tests/score.py",
    "mg_workflow_structured_005": ROOT / "tasks/mg_workflow_structured/task_005_ttbar_pythia_delphes_json/tests/score.py",
    "mg_parse_006": ROOT / "tasks/mg_parse/task_006_mg_log_summary_json/tests/score.py",
    "mg_parse_007": ROOT / "tasks/mg_parse/task_007_mg_failure_diagnosis_json/tests/score.py",
    "mg_parse_008": ROOT / "tasks/mg_parse/task_008_mg_unit_conversion_json/tests/score.py",
    "mg_parse_009": ROOT / "tasks/mg_parse/task_009_mg_output_validation_json/tests/score.py",
    "pythia_config_010": ROOT / "tasks/pythia/task_010_pythia_config_validation_json/tests/score.py",
    "delphes_objects_011": ROOT / "tasks/delphes/task_011_delphes_object_validation_json/tests/score.py",
    "lhe_sanity_012": ROOT / "tasks/lhe/task_012_lhe_sanity_json/tests/score.py",
    "cutflow_diagnosis_013": ROOT / "tasks/analysis/task_013_cutflow_diagnosis_json/tests/score.py",
    "scan_plan_014": ROOT / "tasks/scan/task_014_parameter_scan_plan_json/tests/score.py",
    "param_card_patch_015": ROOT / "tasks/scan/task_015_param_card_patch_json/tests/score.py",
    "scan_results_016": ROOT / "tasks/scan/task_016_scan_results_summary_json/tests/score.py",
    "scan_recovery_017": ROOT / "tasks/scan/task_017_scan_recovery_plan_json/tests/score.py",
    "benchmark_recommendation_018": ROOT / "tasks/scan/task_018_benchmark_recommendation_json/tests/score.py",
    "plot_data_019": ROOT / "tasks/scan/task_019_plot_data_json/tests/score.py",
    "repro_audit_020": ROOT / "tasks/repro/task_020_reproducibility_audit_json/tests/score.py",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True, choices=sorted(TASK_SCORERS))
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    scorer = TASK_SCORERS[args.task]
    cmd = [sys.executable, str(scorer), "--submission", str(args.submission)]
    if args.output:
        cmd.extend(["--output", str(args.output)])

    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
