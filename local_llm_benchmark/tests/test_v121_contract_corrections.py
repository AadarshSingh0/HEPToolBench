"""Regression tests for the prompt-faithful HEPToolBench v1.2.1 contracts."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASIC_SCORER = ROOT / "tasks/mg_basic/task_002_top_pair_freeform/tests/score.py"
WORKFLOW_SCORER = ROOT / "tasks/mg_workflow/task_005_ttbar_pythia_delphes_direct/tests/score.py"
DEBUG_SCORER = ROOT / "tasks/mg_debug/task_002_top_pair_repair/tests/score.py"
BASIC_REFERENCE = ROOT / "tasks/mg_basic/task_002_top_pair_freeform/expected/proc_card.dat"
WORKFLOW_REFERENCE = ROOT / "tasks/mg_workflow/task_005_ttbar_pythia_delphes_direct/expected/mg5_script.txt"


def load_scorer(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load scorer: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASIC = load_scorer(BASIC_SCORER, "v121_basic_scorer")
WORKFLOW = load_scorer(WORKFLOW_SCORER, "v121_workflow_scorer")
DEBUG = load_scorer(DEBUG_SCORER, "v121_debug_scorer")


def score_text(module, text: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        submission = Path(tmp) / "submission.txt"
        submission.write_text(text)
        return module.score_submission(submission)


class BasicContractCorrectionTests(unittest.TestCase):
    def test_reference_answer_still_passes(self) -> None:
        result = score_text(BASIC, BASIC_REFERENCE.read_text())
        self.assertTrue(result["passed"])
        self.assertEqual(result["score"], 1.0)

    def test_prompt_allows_alternative_output_directory(self) -> None:
        text = BASIC_REFERENCE.read_text().replace("output TTbar", "output my_ttbar_run")
        result = score_text(BASIC, text)
        self.assertTrue(result["passed"])
        self.assertEqual(result["score"], 1.0)

    def test_valid_force_and_nested_output_form_passes(self) -> None:
        text = BASIC_REFERENCE.read_text().replace("output TTbar", "output runs/ttbar-v1 -f")
        self.assertTrue(score_text(BASIC, text)["passed"])

    def test_absolute_output_directory_passes(self) -> None:
        text = BASIC_REFERENCE.read_text().replace("output TTbar", "output /tmp/ttbar_run")
        self.assertTrue(score_text(BASIC, text)["passed"])

    def test_missing_output_remains_pass_critical(self) -> None:
        text = BASIC_REFERENCE.read_text().replace("output TTbar\n", "")
        result = score_text(BASIC, text)
        self.assertFalse(result["passed"])
        self.assertIn("missing_or_wrong_output", result["failure_modes"])

    def test_wrong_process_remains_pass_critical(self) -> None:
        text = BASIC_REFERENCE.read_text().replace("p p > t t~", "p p > z")
        result = score_text(BASIC, text)
        self.assertFalse(result["passed"])
        self.assertIn("missing_or_wrong_process", result["failure_modes"])


class DebugCompatibilityTests(unittest.TestCase):
    def test_debug_reference_keeps_historical_output_contract(self) -> None:
        result = score_text(DEBUG, BASIC_REFERENCE.read_text())
        self.assertTrue(result["passed"])
        self.assertIn("has_output_ttbar", result["checks"])

    def test_debug_alternative_output_remains_invalid(self) -> None:
        text = BASIC_REFERENCE.read_text().replace("output TTbar", "output alternate")
        result = score_text(DEBUG, text)
        self.assertFalse(result["passed"])
        self.assertIn("missing_or_wrong_output", result["failure_modes"])


class WorkflowContractCorrectionTests(unittest.TestCase):
    def test_reference_answer_still_passes(self) -> None:
        result = score_text(WORKFLOW, WORKFLOW_REFERENCE.read_text())
        self.assertTrue(result["passed"])
        self.assertEqual(result["score"], 1.0)

    def test_unstated_analysis_switch_is_not_required(self) -> None:
        text = WORKFLOW_REFERENCE.read_text().replace("analysis=OFF\n", "")
        result = score_text(WORKFLOW, text)
        self.assertTrue(result["passed"])
        self.assertEqual(result["score"], 1.0)
        self.assertFalse(result["checks"]["analysis_off_present"])

    def test_unstated_done_marker_is_not_required(self) -> None:
        text = WORKFLOW_REFERENCE.read_text().replace("done\n", "")
        result = score_text(WORKFLOW, text)
        self.assertTrue(result["passed"])
        self.assertEqual(result["score"], 1.0)
        self.assertFalse(result["checks"]["done_present"])

    def test_both_unstated_conventions_may_be_absent(self) -> None:
        text = WORKFLOW_REFERENCE.read_text().replace("analysis=OFF\n", "").replace("done\n", "")
        result = score_text(WORKFLOW, text)
        self.assertTrue(result["passed"])
        self.assertEqual(result["score"], 1.0)

    def test_requested_madspin_state_remains_pass_critical(self) -> None:
        text = WORKFLOW_REFERENCE.read_text().replace("madspin=OFF\n", "")
        result = score_text(WORKFLOW, text)
        self.assertFalse(result["passed"])
        self.assertIn("wrong_or_missing_madspin", result["failure_modes"])

    def test_requested_shower_remains_pass_critical(self) -> None:
        text = WORKFLOW_REFERENCE.read_text().replace("shower=Pythia8", "shower=OFF")
        result = score_text(WORKFLOW, text)
        self.assertFalse(result["passed"])
        self.assertIn("wrong_or_missing_shower", result["failure_modes"])

    def test_requested_event_count_remains_pass_critical(self) -> None:
        text = WORKFLOW_REFERENCE.read_text().replace("set nevents 10000", "set nevents 1000")
        result = score_text(WORKFLOW, text)
        self.assertFalse(result["passed"])
        self.assertIn("wrong_or_missing_nevents", result["failure_modes"])


if __name__ == "__main__":
    unittest.main()
