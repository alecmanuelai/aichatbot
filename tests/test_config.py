import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from config import AppConfig, ConfigurationError, PROJECT_DIR


class ConfigTests(unittest.TestCase):
    def test_defaults_and_dotenv_precedence(self):
        with TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            directory = Path(tmp)
            self.assertEqual(AppConfig.load(directory).mode, "offline")
            (directory / ".env").write_text("AI_MODE=offline\nAI_TIMEOUT_SECONDS=12\n")
            self.assertEqual(AppConfig.load(directory).timeout_seconds, 12)
            os.environ["AI_TIMEOUT_SECONDS"] = "15"
            self.assertEqual(AppConfig.load(directory).timeout_seconds, 15)

    def test_project_path_is_absolute_and_key_not_in_repr(self):
        self.assertTrue(PROJECT_DIR.is_absolute())
        self.assertNotIn("example-secret", repr(AppConfig(api_key="example-secret")))

    def test_online_configuration_and_endpoint(self):
        config = AppConfig("online", "https://api.example.com/v1/", "test-key", "test-model")
        config.validate()
        self.assertEqual(config.endpoint, "https://api.example.com/v1/chat/completions")

    def test_invalid_modes_missing_values_and_timeouts(self):
        configs = [AppConfig(mode="auto"), AppConfig(mode="online")]
        configs += [AppConfig(timeout_seconds=value) for value in (0, 121, float("nan"), float("inf"))]
        for config in configs:
            with self.subTest(config=config), self.assertRaises(ConfigurationError):
                config.validate()
        with TemporaryDirectory() as tmp, patch.dict(os.environ, {"AI_TIMEOUT_SECONDS": "not-a-number"}, clear=True):
            with self.assertRaises(ConfigurationError):
                AppConfig.load(Path(tmp))

    def test_insecure_malformed_or_complete_endpoint_rejected(self):
        urls = ["http://example.com/v1", "https://user:password@example.com/v1", "https://example.com?key=secret",
                "https://example.com/#fragment", "https://example.com:bad", "https://", "https://exa mple.com",
                "https://example.com/v1/chat/completions", "https://[broken",
                "https://@example.com/v1", "https://example.com?", "https://example.com#"]
        for url in urls:
            with self.subTest(url=url), self.assertRaises(ConfigurationError):
                AppConfig("online", url, "test-key", "test-model").validate()

    def test_placeholders_rejected_in_online_mode(self):
        with self.assertRaises(ConfigurationError):
            AppConfig("online", "https://api.example.com/v1", "replace_with_key", "test-model").validate()
