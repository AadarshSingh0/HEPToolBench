import os
import unittest

from runners.ollama_generation_settings import (
    ENV_NUM_PREDICT,
    ENV_SEED,
    ENV_TEMPERATURE,
    ENV_THINK,
    build_ollama_options,
    get_ollama_think,
)


class OllamaGenerationSettingsTests(unittest.TestCase):

    ENV_NAMES = (
        ENV_THINK,
        ENV_TEMPERATURE,
        ENV_SEED,
        ENV_NUM_PREDICT,
    )

    def setUp(self):
        self.saved = {
            name: os.environ.get(name)
            for name in self.ENV_NAMES
        }

        for name in self.ENV_NAMES:
            os.environ.pop(name, None)

    def tearDown(self):
        for name, value in self.saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_defaults_only_send_num_ctx(self):
        self.assertIsNone(get_ollama_think())

        self.assertEqual(
            build_ollama_options(4096),
            {"num_ctx": 4096},
        )

    def test_explicit_overrides(self):
        os.environ[ENV_THINK] = "false"
        os.environ[ENV_TEMPERATURE] = "0.2"
        os.environ[ENV_SEED] = "7"
        os.environ[ENV_NUM_PREDICT] = "2048"

        self.assertIs(
            get_ollama_think(),
            False,
        )

        self.assertEqual(
            build_ollama_options(8192),
            {
                "num_ctx": 8192,
                "temperature": 0.2,
                "seed": 7,
                "num_predict": 2048,
            },
        )

    def test_think_true(self):
        os.environ[ENV_THINK] = "true"
        self.assertIs(get_ollama_think(), True)

    def test_thinking_levels(self):
        for value in ("low", "medium", "high", "max"):
            os.environ[ENV_THINK] = value
            self.assertEqual(
                get_ollama_think(),
                value,
            )

    def test_auto_omits_overrides(self):
        os.environ[ENV_THINK] = "auto"
        os.environ[ENV_TEMPERATURE] = "auto"
        os.environ[ENV_SEED] = "auto"
        os.environ[ENV_NUM_PREDICT] = "auto"

        self.assertIsNone(get_ollama_think())

        self.assertEqual(
            build_ollama_options(4096),
            {"num_ctx": 4096},
        )

    def test_invalid_think_rejected(self):
        os.environ[ENV_THINK] = "banana"

        with self.assertRaises(ValueError):
            get_ollama_think()

    def test_negative_temperature_rejected(self):
        os.environ[ENV_TEMPERATURE] = "-0.1"

        with self.assertRaises(ValueError):
            build_ollama_options(4096)

    def test_zero_num_predict_rejected(self):
        os.environ[ENV_NUM_PREDICT] = "0"

        with self.assertRaises(ValueError):
            build_ollama_options(4096)

    def test_invalid_seed_rejected(self):
        os.environ[ENV_SEED] = "not-an-integer"

        with self.assertRaises(ValueError):
            build_ollama_options(4096)


if __name__ == "__main__":
    unittest.main()
