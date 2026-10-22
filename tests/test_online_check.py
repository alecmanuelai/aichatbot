from dataclasses import replace
import io
import unittest
from unittest.mock import MagicMock, patch

import requests

from backend.ai_service import AIService, SYSTEM_INSTRUCTION
from check_online import CHAT_PROMPT, GEMINI_NATIVE_ROOT, GEMINI_ROOT, check_chat, check_connection, main
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


class ChatCheckTests(unittest.TestCase):
    def setUp(self):
        self.config = AppConfig("online", GEMINI_ROOT, "private-test-key", "gemini-example-flash", 120)
        self.output = []
        patcher = patch("check_online.requests.Session")
        self.factory = patcher.start()
        self.addCleanup(patcher.stop)
        self.session = self.factory.return_value.__enter__.return_value
        self.response = MagicMock()
        self.response.status_code = 200
        self.response.json.return_value = {"choices": [{"message": {"content": "StudyBuddy is online."}}]}
        self.session.post.return_value.__enter__.return_value = self.response

    def run_check(self, config=None):
        return check_chat(config or self.config, report=self.output.append)

    def test_one_secure_synthetic_request_matches_a_new_app_chat(self):
        self.assertEqual(self.run_check(), 0)
        self.session.post.assert_called_once_with(
            GEMINI_ROOT + "/chat/completions",
            json={"model": self.config.model, "messages": AIService.build_context([
                {"role": "user", "content": CHAT_PROMPT},
            ])},
            timeout=(10, 120), verify=True, allow_redirects=False,
        )
        self.session.get.assert_not_called()
        prepared = requests.Request("POST", self.config.endpoint).prepare()
        self.session.auth(prepared)
        self.assertEqual(prepared.headers["Authorization"], "Bearer private-test-key")
        self.assertIn("Chat generation succeeded", "\n".join(self.output))

    def test_chat_requires_explicit_command_line_flag(self):
        with patch("check_online.AppConfig.load", return_value=self.config), \
                patch("check_online.check_connection", return_value=0) as model_check, \
                patch("check_online.check_chat", return_value=1) as chat_check:
            self.assertEqual(main([]), 0)
            model_check.assert_called_once_with(self.config)
            chat_check.assert_not_called()
            self.assertEqual(main(["--chat"]), 1)
            chat_check.assert_called_once_with(self.config)
            chat_check.reset_mock()
            self.assertEqual(main(["--native-chat"]), 1)
            chat_check.assert_called_once_with(self.config, native=True)
        self.factory.assert_not_called()

    def test_conflicting_chat_flags_do_not_send_two_requests(self):
        with patch("check_online.AppConfig.load") as config_load, patch("sys.stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as error:
                main(["--chat", "--native-chat"])
            self.assertEqual(error.exception.code, 2)
            config_load.assert_not_called()
        self.factory.assert_not_called()

    def test_native_request_uses_header_key_and_generate_content_schema(self):
        self.response.json.return_value = {"candidates": [{"content": {"parts": [
            {"thought": True, "text": "private reasoning"},
            {"text": "StudyBuddy is online."},
        ]}}]}
        config = replace(self.config, model="models/gemini-example-flash")
        self.assertEqual(check_chat(config, self.output.append, native=True), 0)
        endpoint = GEMINI_NATIVE_ROOT + "/models/gemini-example-flash:generateContent"
        self.session.post.assert_called_once_with(
            endpoint,
            json={
                "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
                "contents": [{"role": "user", "parts": [{"text": CHAT_PROMPT}]}],
            },
            timeout=(10, 120), verify=True, allow_redirects=False,
        )
        self.session.get.assert_not_called()
        prepared = requests.Request("POST", endpoint, headers={"Authorization": "Basic obsolete"}).prepare()
        self.session.auth(prepared)
        self.assertEqual(prepared.headers["x-goog-api-key"], self.config.api_key)
        self.assertNotIn("Authorization", prepared.headers)
        self.assertNotIn(self.config.api_key, prepared.url)
        text = "\n".join(self.output)
        self.assertIn("Native Gemini chat generation succeeded", text)
        self.assertIn("still uses the compatibility endpoint", text)
        self.assertNotIn("private reasoning", text)
        self.assertNotIn(self.config.api_key, text)

    def test_native_response_requires_answer_text(self):
        cases = [None, {}, {"candidates": []},
                 {"candidates": [{"content": {"parts": None}}]},
                 {"candidates": [{"content": {"parts": []}}]},
                 {"candidates": [{"content": {"parts": [{"text": " "}]}}]},
                 {"candidates": [{"content": {"parts": [{"text": "private-test-key", "thought": True}]}}]},
                 {"candidates": [{"content": {"parts": [None, {"text": 4}, {"functionCall": {}}]}}]}]
        for payload in cases:
            with self.subTest(payload=payload):
                self.output.clear()
                self.response.json.return_value = payload
                self.assertEqual(check_chat(self.config, self.output.append, native=True), 1)
                text = "\n".join(self.output)
                self.assertIn("no usable text", text)
                self.assertNotIn(self.config.api_key, text)

    def test_native_errors_are_safe_without_fallback_requests(self):
        for status, google_status in ((400, "INVALID_ARGUMENT"), (403, "PERMISSION_DENIED"),
                                      (404, "NOT_FOUND"), (429, "RESOURCE_EXHAUSTED"),
                                      (503, "UNAVAILABLE"), (302, "UNKNOWN")):
            with self.subTest(status=status):
                self.session.post.reset_mock()
                self.output.clear()
                self.response.status_code = status
                self.response.json.return_value = {"error": {"status": google_status, "message": "private-test-key"}}
                self.assertEqual(check_chat(self.config, self.output.append, native=True), 1)
                self.session.post.assert_called_once()
                text = "\n".join(self.output)
                self.assertIn(f"HTTP status: {status}", text)
                self.assertNotIn(self.config.api_key, text)
                self.assertNotIn("succeeded", text)
        self.session.get.assert_not_called()

    def test_native_invalid_model_ids_are_not_used_in_urls(self):
        for model in ("other-model", "gemini-x/../../models/other", "gemini-x?key=secret", "gemini-x\n", "models/"):
            with self.subTest(model=model):
                self.assertEqual(check_chat(replace(self.config, model=model), self.output.append, native=True), 1)
        self.factory.assert_not_called()

    def test_error_details_are_classified_without_printing_private_fields(self):
        self.response.status_code = 400
        self.response.json.return_value = {"error": {
            "status": "INVALID_ARGUMENT", "message": "API key not valid. private-test-key",
            "details": [{"reason": "API_KEY_INVALID", "metadata": {"key": "private-test-key"}}],
        }}
        self.assertEqual(self.run_check(), 1)
        text = "\n".join(self.output)
        self.assertIn("HTTP status: 400", text)
        self.assertIn("Google error status: INVALID_ARGUMENT", text)
        self.assertIn("Google error reason: API_KEY_INVALID", text)
        self.assertIn("API key is invalid", text)
        self.assertNotIn("private-test-key", text)

    def test_known_model_region_billing_and_role_errors_have_fixed_explanations(self):
        cases = [
            ("model is not supported for generateContent private-test-key", "missing or unsupported"),
            ("User location is not supported private-test-key", "current region"),
            ("Please enable billing private-test-key", "requires billing"),
            ("Roles must alternate between user and model private-test-key", "role ordering"),
        ]
        for message, expected in cases:
            with self.subTest(expected=expected):
                self.output.clear()
                self.response.status_code = 400
                self.response.json.return_value = [{"error": {"message": message}}]
                self.assertEqual(self.run_check(), 1)
                self.assertIn(expected, "\n".join(self.output))
                self.assertNotIn("private-test-key", "\n".join(self.output))

    def test_unknown_errors_and_malformed_details_are_safe(self):
        for payload in (None, [], {"error": None}, {"error": {
            "status": "private-test-key", "message": "private-test-key",
            "details": [{"reason": "private-test-key"}, None, {"reason": []}],
        }}, {"error": {"status": [], "message": {}, "details": "private-test-key"}}):
            with self.subTest(payload=payload):
                self.output.clear()
                self.response.status_code = 400
                self.response.json.return_value = payload
                self.assertEqual(self.run_check(), 1)
                self.assertNotIn("private-test-key", "\n".join(self.output))
        self.response.json.side_effect = ValueError("private-test-key")
        self.assertEqual(self.run_check(), 1)
        self.assertNotIn("private-test-key", "\n".join(self.output))

    def test_http_rejections_are_not_reported_as_success(self):
        for status in (302, 400, 401, 403, 404, 408, 429, 500, 503, 504):
            with self.subTest(status=status):
                self.output.clear()
                self.response.status_code = status
                self.assertEqual(self.run_check(), 1)
                self.assertIn(f"HTTP status: {status}", self.output)
                self.assertNotIn("succeeded", "\n".join(self.output))

    def test_malformed_or_empty_success_responses_do_not_claim_working_chat(self):
        for payload in (None, {}, {"choices": []}, {"choices": [{"message": {"content": " "}}]},
                        {"choices": [{"message": {"content": ["unexpected"]}}]}):
            with self.subTest(payload=payload):
                self.response.json.return_value = payload
                self.assertEqual(self.run_check(), 1)
        self.response.json.side_effect = ValueError("private-test-key")
        self.assertEqual(self.run_check(), 1)
        self.assertNotIn("private-test-key", "\n".join(self.output))

    def test_transport_errors_are_safe_and_not_retried(self):
        errors = [requests.ConnectTimeout, requests.ReadTimeout, requests.Timeout,
                  requests.exceptions.SSLError, requests.exceptions.ProxyError, requests.ConnectionError]
        for native in (False, True):
            for error in errors:
                with self.subTest(error=error.__name__, native=native):
                    self.session.post.reset_mock()
                    self.output.clear()
                    self.session.post.side_effect = error("private-test-key")
                    self.assertEqual(check_chat(self.config, self.output.append, native=native), 1)
                    self.session.post.assert_called_once()
                    self.assertNotIn("private-test-key", "\n".join(self.output))

    def test_invalid_config_never_sends_a_chat_request(self):
        for config in (AppConfig(), AppConfig(mode="online"),
                       AppConfig("online", "https://example.com/v1beta/openai", "test-key", "model")):
            self.assertEqual(self.run_check(config), 1)
            self.assertEqual(check_chat(config, self.output.append, native=True), 1)
        self.factory.assert_not_called()
