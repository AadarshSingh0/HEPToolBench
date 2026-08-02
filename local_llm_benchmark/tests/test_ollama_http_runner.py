#!/usr/bin/env python3
"""Offline smoke tests for the corrected Ollama transport and runner."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import types
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

io_utils_stub = types.ModuleType("runners.io_utils")
io_utils_stub.ensure_output_dirs = lambda: None
sys.modules.setdefault("runners.io_utils", io_utils_stub)
scripts_stub = types.ModuleType("scripts")
scripts_stub.__path__ = []
csv_stub = types.ModuleType("scripts.build_universal_csv")
csv_stub.rebuild_outputs = lambda quiet=False: None
sys.modules.setdefault("scripts", scripts_stub)
sys.modules.setdefault("scripts.build_universal_csv", csv_stub)

from runners import run_ollama_task as runner  # noqa: E402
import run_benchmark as benchmark  # noqa: E402
from runners.ollama_http_transport import (  # noqa: E402
    OllamaOutputContaminationError,
    clear_model_caches,
)


class MockOllamaHandler(BaseHTTPRequestHandler):
    output_text = '{"status":"ok"}'
    done_reason = "stop"
    last_generate_payload: dict | None = None

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/api/tags":
            self._send_json(
                {
                    "models": [
                        {
                            "name": "test:latest",
                            "model": "test:latest",
                            "digest": "sha256:test-digest",
                            "size": 123,
                            "modified_at": "2026-07-30T00:00:00Z",
                            "details": {
                                "family": "test",
                                "parameter_size": "1B",
                                "quantization_level": "Q4_K_M",
                            },
                        }
                    ]
                }
            )
            return
        self._send_json({"error": "not found"}, status=404)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        if self.path == "/api/show":
            self._send_json(
                {
                    "capabilities": ["completion"],
                    "parameters": "temperature 0.8",
                    "template": "test template",
                    "modelfile": "FROM test",
                    "model_info": {"test.context_length": 8192},
                }
            )
            return
        if self.path == "/api/generate":
            type(self).last_generate_payload = payload
            self._send_json(
                {
                    "model": "test:latest",
                    "created_at": "2026-07-30T00:00:00Z",
                    "response": type(self).output_text,
                    "done": True,
                    "done_reason": type(self).done_reason,
                    "prompt_eval_count": 10,
                    "eval_count": 5,
                    "total_duration": 100,
                }
            )
            return
        self._send_json({"error": "not found"}, status=404)


class OllamaHTTPRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), MockOllamaHandler)
        cls.thread = threading.Thread(
            target=cls.server.serve_forever,
            daemon=True,
        )
        cls.thread.start()
        cls.host = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.thread.join(timeout=5)
        cls.server.server_close()

    def setUp(self) -> None:
        clear_model_caches()
        MockOllamaHandler.output_text = '{"status":"ok"}'
        MockOllamaHandler.done_reason = "stop"
        MockOllamaHandler.last_generate_payload = None
        self.old_host = os.environ.get("OLLAMA_HOST")
        os.environ["OLLAMA_HOST"] = self.host
        self.old_tasks = runner.TASKS
        self.old_evaluate = runner.evaluate
        runner.TASKS = {"unit_test": {"artifact": "answer.json"}}
        runner.evaluate = lambda task_id, submission, result_path: {
            "task_id": task_id,
            "score": 1.0,
            "passed": True,
            "failure_modes": [],
        }
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()
        runner.TASKS = self.old_tasks
        runner.evaluate = self.old_evaluate
        if self.old_host is None:
            os.environ.pop("OLLAMA_HOST", None)
        else:
            os.environ["OLLAMA_HOST"] = self.old_host

    def run_attempt(self) -> dict:
        return runner.run_single_attempt(
            model="test:latest",
            task_id="unit_test",
            prompt="Return JSON.\n",
            timeout=5,
            submission_dir=self.root / "submission",
            result_path=self.root / "result.json",
            num_ctx=4096,
        )

    def test_non_streaming_http_success_and_metadata(self) -> None:
        result = self.run_attempt()
        self.assertEqual(result["score"], 1.0)
        self.assertTrue(result["valid_for_scoring"])
        self.assertEqual(result["ollama_model_digest"], "sha256:test-digest")
        self.assertEqual(
            (self.root / "submission/answer.json").read_text(),
            '{"status":"ok"}\n',
        )
        payload = MockOllamaHandler.last_generate_payload
        self.assertIsNotNone(payload)
        self.assertIs(payload["stream"], False)
        self.assertEqual(payload["options"], {"num_ctx": 4096})
        metadata = json.loads(
            (self.root / "submission/ollama_http_metadata.json").read_text()
        )
        self.assertEqual(
            metadata["output"]["control_characters"]["forbidden_total"],
            0,
        )

    def test_control_character_is_rejected_before_artifact_write(self) -> None:
        MockOllamaHandler.output_text = '{"value":"bad\x1b[5D"}'
        with self.assertRaises(OllamaOutputContaminationError):
            self.run_attempt()
        self.assertFalse((self.root / "submission/answer.json").exists())
        metadata = json.loads(
            (self.root / "submission/ollama_http_metadata.json").read_text()
        )
        self.assertEqual(
            metadata["error"]["failure_mode"],
            "ollama_output_control_characters",
        )
        result = json.loads((self.root / "result.json").read_text())
        self.assertIs(result["valid_for_scoring"], False)
        self.assertIsNone(result["score"])

    def test_length_stop_is_recorded_as_truncation(self) -> None:
        MockOllamaHandler.done_reason = "length"
        result = self.run_attempt()
        self.assertTrue(result["ollama_output_truncated"])


class RunIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.tempdir.name)
        self.old_tasks = benchmark.TASKS
        benchmark.TASKS = {"task_001": {"artifact": "answer.txt"}}
        self.model = "test:latest"
        self.digest = "sha256:test-digest"

        result_path = benchmark.result_path_for(
            self.run_dir,
            self.model,
            "task_001",
            1,
        )
        result_path.parent.mkdir(parents=True)
        result_path.write_text(
            json.dumps(
                {
                    "run_id": "test-run",
                    "model": self.model,
                    "task_id": "task_001",
                    "repeat": 1,
                    "score": 1.0,
                    "passed": True,
                    "valid_for_scoring": True,
                    "runner_error": False,
                    "timeout": False,
                    "ollama_output_truncated": False,
                    "ollama_model_digest": self.digest,
                }
            )
        )
        submission_dir = benchmark.submission_dir_for(
            self.run_dir,
            self.model,
            "task_001",
            1,
        )
        submission_dir.mkdir(parents=True)
        (submission_dir / "answer.txt").write_text("clean\n")
        (submission_dir / "ollama_http_metadata.json").write_text("{}\n")

    def tearDown(self) -> None:
        benchmark.TASKS = self.old_tasks
        self.tempdir.cleanup()

    def audit(self) -> dict:
        return benchmark.audit_run_integrity(
            run_dir=self.run_dir,
            models=[self.model],
            tasks=["task_001"],
            repeats=1,
            model_identities={self.model: {"digest": self.digest}},
        )

    def test_complete_clean_run_passes_integrity_audit(self) -> None:
        audit = self.audit()
        self.assertTrue(audit["passed"])
        self.assertEqual(
            audit["checks"]["observed_unique_evaluations"],
            1,
        )

    def test_contaminated_artifact_fails_integrity_audit(self) -> None:
        artifact = (
            benchmark.submission_dir_for(
                self.run_dir,
                self.model,
                "task_001",
                1,
            )
            / "answer.txt"
        )
        artifact.write_text("bad\x1b[5D\n")
        audit = self.audit()
        self.assertFalse(audit["passed"])
        self.assertEqual(
            len(audit["checks"]["contaminated_artifacts"]),
            1,
        )

    def test_digest_change_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            benchmark.verify_model_identities(
                {self.model: {"digest": self.digest}},
                {self.model: {"digest": "sha256:changed"}},
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
