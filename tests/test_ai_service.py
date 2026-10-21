import unittest
from unittest.mock import MagicMock, patch

import requests

from backend.ai_service import AIService, AIServiceError, OFFLINE_PREFIX, SYSTEM_INSTRUCTION
from config import AppConfig


class AIServiceTests(unittest.TestCase):
    def setUp(self):
        self.ai = AIService(AppConfig("online", "https://api.example.com/v1/", "test-secret", "test-model", 15))
        self.messages = [{"role": "user", "content": "Explain Python"}]
        patcher = patch("backend.ai_service.requests.Session")
        self.session_factory = patcher.start()
        self.addCleanup(patcher.stop)
        self.session = self.session_factory.return_value.__enter__.return_value
        self.response = MagicMock()
        self.response.status_code = 200
        self.response.__enter__.return_value = self.response
        self.response.json.return_value = {"choices": [{"message": {"content": "  A helpful answer.  "}}]}
        self.session.post.return_value = self.response

    def test_real_request_shape_and_secure_options(self):
        self.assertEqual(self.ai.reply(self.messages), "A helpful answer.")
        args, kwargs = self.session.post.call_args
        self.assertEqual(args[0], "https://api.example.com/v1/chat/completions")
        self.assertTrue(kwargs["verify"])
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(kwargs["timeout"], 15)
        self.assertEqual(kwargs["json"]["model"], "test-model")
        self.assertEqual(kwargs["json"]["messages"][0], {"role": "system", "content": SYSTEM_INSTRUCTION})
        prepared = requests.Request("POST", args[0]).prepare()
        self.session.auth(prepared)
        self.assertEqual(prepared.headers["Authorization"], "Bearer test-secret")
        self.assertNotIn("test-secret", str(kwargs["json"]))

    def test_context_preserves_history_but_excludes_demo_answers(self):
        messages = [
            {"role": "user", "content": "Question one", "id": 1},
            {"role": "assistant", "content": OFFLINE_PREFIX + "\nDemo"},
            {"role": "user", "content": "Question two"},
            {"role": "assistant", "content": "Actual online answer"},
            {"role": "system", "content": "Unexpected stored instruction"},
        ]
        context = self.ai.build_context(messages)
        self.assertEqual([m["role"] for m in context], ["system", "user", "user", "assistant"])
        self.assertEqual(context[-1]["content"], "Actual online answer")
        self.assertTrue(all(set(m) == {"role", "content"} for m in context))

    def test_http_errors_are_safe_and_never_fall_back(self):
        for status, phrase in [(401, "rejected access"), (403, "rejected access"), (429, "quota"),
                               (408, "timed out"), (504, "timed out"), (500, "server problem"),
                               (302, "redirected"), (400, "rejected the request")]:
            self.response.status_code = status
            self.response.text = "sensitive raw body test-secret"
            with self.subTest(status=status), self.assertRaises(AIServiceError) as error:
                self.ai.reply(self.messages)
            self.assertIn(phrase, str(error.exception))
            self.assertNotIn("test-secret", str(error.exception))
            self.assertNotIn(OFFLINE_PREFIX, str(error.exception))

    def test_transport_errors_are_safe(self):
        for error, phrase in [(requests.Timeout("secret"), "timed out"),
                             (requests.exceptions.SSLError("secret"), "verified"),
                             (requests.ConnectionError("secret"), "Cannot reach")]:
            self.session.post.side_effect = error
            with self.subTest(error=type(error).__name__), self.assertRaises(AIServiceError) as caught:
                self.ai.reply(self.messages)
            self.assertIn(phrase, str(caught.exception))
            self.assertNotIn("secret", str(caught.exception))

    def test_unexpected_or_empty_json(self):
        bodies = [None, [], {}, {"choices": []}, {"choices": [{}]},
                  {"choices": [{"message": {"content": " "}}]},
                  {"choices": [{"message": {"content": ["not text"]}}]}]
        for body in bodies:
            self.response.json.return_value = body
            with self.subTest(body=body), self.assertRaisesRegex(AIServiceError, "unexpected"):
                self.ai.reply(self.messages)
        self.response.json.side_effect = ValueError("sensitive response")
        with self.assertRaisesRegex(AIServiceError, "unexpected"):
            self.ai.reply(self.messages)

    def test_offline_examples_are_labelled_and_never_use_network(self):
        offline = AIService(AppConfig())
        answers = []
        for question in ("SQLite", "Python classes", "API", "algebra", "exam tips", "hello"):
            answer = offline.reply([{"role": "user", "content": question}])
            self.assertTrue(answer.startswith(OFFLINE_PREFIX))
            answers.append(answer)
        self.assertEqual(len(set(answers)), 6)
        self.session_factory.assert_not_called()
