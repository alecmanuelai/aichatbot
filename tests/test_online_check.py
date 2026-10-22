import unittest
from unittest.mock import MagicMock, patch

import requests

from check_online import GEMINI_ROOT, check_connection
from config import AppConfig


class OnlineCheckTests(unittest.TestCase):
    def setUp(self):
        self.config = AppConfig("online", GEMINI_ROOT, "private-test-key", "gemini-example-flash")
        self.output = []
        patcher = patch("check_online.requests.Session")
        self.factory = patcher.start()
        self.addCleanup(patcher.stop)
        self.session = self.factory.return_value.__enter__.return_value
        self.response = MagicMock()
        self.response.status_code = 200
        self.response.json.return_value = {"data": [{"id": "models/gemini-example-flash"}]}
        self.session.get.return_value.__enter__.return_value = self.response

    def run_check(self, config=None):
        return check_connection(config or self.config, report=self.output.append)

    def test_model_access_request_is_secure_and_does_not_generate_chat(self):
        self.assertEqual(self.run_check(), 0)
        args, kwargs = self.session.get.call_args
        self.assertEqual(args, (GEMINI_ROOT + "/models",))
        self.assertTrue(kwargs["verify"])
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(kwargs["timeout"], (10, 20))
        prepared = requests.Request("GET", args[0]).prepare()
        self.session.auth(prepared)
        self.assertEqual(prepared.headers["Authorization"], "Bearer private-test-key")
        self.session.post.assert_not_called()
        self.assertIn("Configured model listed: yes", self.output)
        self.assertIn("  gemini-example-flash", self.output)
        self.assertNotIn(self.config.api_key, "\n".join(self.output))

    def test_missing_model_does_not_claim_chat_is_ready(self):
        self.response.json.return_value = {"data": [{"id": "gemini-different-flash"}]}
        self.assertEqual(self.run_check(), 1)
        self.assertIn("Configured model listed: no", self.output)
        self.assertIn("  gemini-different-flash", self.output)

    def test_http_failures_never_print_sensitive_response_bodies(self):
        for status in (400, 401, 403, 404, 408, 429, 500, 504, 302):
            with self.subTest(status=status):
                self.output.clear()
                self.response.status_code = status
                self.response.text = "sensitive provider response private-test-key"
                self.assertEqual(self.run_check(), 1)
                self.assertIn(f"HTTP status: {status}", self.output)
                self.assertNotIn("private-test-key", "\n".join(self.output))
        self.response.json.assert_not_called()

    def test_transport_failures_are_distinguished_without_exception_details(self):
        errors = [(requests.ConnectTimeout, "Connection timed out"),
                  (requests.ReadTimeout, "Reading the model list timed out"),
                  (requests.exceptions.SSLError, "TLS certificate verification failed"),
                  (requests.exceptions.ProxyError, "proxy could not reach"),
                  (requests.Timeout, "model-list request timed out"),
                  (requests.ConnectionError, "could not be reached")]
        for error, expected in errors:
            with self.subTest(error=error.__name__):
                self.output.clear()
                self.session.get.side_effect = error("private-test-key")
                self.assertEqual(self.run_check(), 1)
                self.assertIn(expected, "\n".join(self.output))
                self.assertNotIn("private-test-key", "\n".join(self.output))

    def test_empty_or_malformed_json_is_reported_safely(self):
        for payload in (None, [], {}, {"data": None}, {"data": []}, {"data": [None, "unexpected"]}):
            with self.subTest(payload=payload):
                self.output.clear()
                self.response.json.return_value = payload
                self.assertEqual(self.run_check(), 1)
                self.assertIn("unexpected model list", "\n".join(self.output))
        self.response.json.side_effect = ValueError("private-test-key")
        self.assertEqual(self.run_check(), 1)
        self.assertNotIn("private-test-key", "\n".join(self.output))

    def test_invalid_config_or_other_host_does_not_receive_the_key(self):
        configs = [AppConfig(), AppConfig(mode="online"),
                   AppConfig("online", "http://example.com", "test-key", "model"),
                   AppConfig("online", "https://example.com/v1beta/openai", "test-key", "model"),
                   AppConfig("online", "https://generativelanguage.googleapis.com:8443/v1beta/openai", "test-key", "model"),
                   AppConfig("online", "https://generativelanguage.googleapis.com/wrong", "test-key", "model")]
        for config in configs:
            with self.subTest(mode=config.mode):
                self.assertEqual(self.run_check(config), 1)
        self.factory.assert_not_called()

    def test_model_identifiers_are_filtered_before_display(self):
        self.response.json.return_value = {"data": [
            {"id": "models/gemini-example-flash"}, {"id": "gemini-bad\nunsafe"},
            {"id": "gemini-private-test-key-flash"}, {"id": "arbitrary provider text"},
            {"id": 42}, None,
        ]}
        self.assertEqual(self.run_check(), 0)
        text = "\n".join(self.output)
        self.assertNotIn("private-test-key", text)
        self.assertNotIn("arbitrary provider text", text)
        self.assertNotIn("unsafe", text)
