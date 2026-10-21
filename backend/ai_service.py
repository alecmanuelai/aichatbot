"""Predefined classroom demo or a real OpenAI-compatible HTTPS request."""

import requests

from config import AppConfig

# This exact label also lets online context exclude stored demo output after a restart.
OFFLINE_PREFIX = "[OFFLINE DEMO — predefined response]"
SYSTEM_INSTRUCTION = (
    "You are StudyBuddy, a helpful student study assistant. Explain concepts clearly, "
    "use small examples, encourage learning rather than cheating, and acknowledge uncertainty. "
    "Use readable plain text because this desktop app does not render Markdown."
)


class AIServiceError(Exception):
    """Only deliberately safe messages should be placed in this exception."""


class BearerAuth(requests.auth.AuthBase):
    """Use the configured key instead of credentials from a user's netrc file."""

    def __init__(self, api_key: str):
        self._api_key = api_key

    def __call__(self, request):
        request.headers["Authorization"] = f"Bearer {self._api_key}"
        return request


class AIService:
    def __init__(self, config: AppConfig):
        config.validate()
        self.config = config

    @staticmethod
    def build_context(messages: list[dict]) -> list[dict]:
        context = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
        for message in messages:
            role, content = message["role"], message["content"]
            if role not in {"user", "assistant"}:
                continue
            if role == "assistant" and content.startswith(OFFLINE_PREFIX):
                continue
            context.append({"role": role, "content": content})
        return context

    def reply(self, messages: list[dict]) -> str:
        if self.config.mode == "offline":
            return self.offline_reply(messages)
        context = self.build_context(messages)
        try:
            # Honor managed HTTPS proxies and CA bundles; never follow redirects.
            with requests.Session() as session:
                session.auth = BearerAuth(self.config.api_key)
                response = session.post(
                    self.config.endpoint,
                    json={"model": self.config.model, "messages": context},
                    timeout=self.config.timeout_seconds,
                    verify=True,
                    allow_redirects=False,
                )
                with response:
                    status = response.status_code
                    if status in {401, 403}:
                        raise AIServiceError("The provider rejected access. Check your API key and model permissions in .env.")
                    if status == 429:
                        raise AIServiceError("The provider's rate or quota limit was reached. Wait, check your quota, then retry.")
                    if status in {408, 504}:
                        raise AIServiceError("The provider timed out. Please retry in a moment.")
                    if status >= 500:
                        raise AIServiceError("The AI provider has a server problem. Please retry later.")
                    if 300 <= status < 400:
                        raise AIServiceError("The provider redirected the request. Set AI_BASE_URL to its final HTTPS API root.")
                    if not 200 <= status < 300:
                        raise AIServiceError("The provider rejected the request. Check the API root, model, and conversation size.")
                    try:
                        data = response.json()
                        content = data["choices"][0]["message"]["content"]
                        if not isinstance(content, str) or not content.strip():
                            raise ValueError
                    except (ValueError, KeyError, IndexError, TypeError):
                        raise AIServiceError("The provider returned an empty or unexpected response. Please retry.") from None
                    return content.strip()
        except requests.Timeout:
            raise AIServiceError("The request timed out. Check your connection and retry.") from None
        except requests.exceptions.SSLError:
            raise AIServiceError("The secure connection could not be verified. Check your clock and certificate setup; do not disable TLS verification.") from None
        except requests.RequestException:
            raise AIServiceError("Cannot reach the AI provider. Check your network and HTTPS API root, then retry.") from None

    @staticmethod
    def offline_reply(messages: list[dict]) -> str:
        text = next((m["content"].lower() for m in reversed(messages) if m["role"] == "user"), "")
        if any(word in text for word in ("sqlite", "database", "sql")):
            answer = (
                "SQLite stores structured data in a local file. A table has rows and columns. "
                "StudyBuddy has conversations and messages tables, linked by conversation_id.\n\n"
                "Example: SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id;\n\n"
                "The ? is a parameter: values are supplied separately to avoid SQL injection."
            )
        elif any(word in text for word in ("python", "class", "function")):
            answer = (
                "A Python class groups related data and methods. An object is one instance of a class.\n\n"
                "For example, DatabaseManager stores the database path and provides methods such as "
                "get_messages(). A function performs one task; a method is a function belonging to a class.\n\n"
                "Try explaining the difference between a class and an object in your own words."
            )
        elif any(word in text for word in ("api", "network", "online")):
            answer = (
                "An API is a structured way for programs to communicate. In online mode, StudyBuddy "
                "sends conversation messages as JSON over verified HTTPS to a model provider.\n\n"
                "The key stays in your private .env file. This offline response did not contact a model."
            )
        elif any(word in text for word in ("math", "algebra", "equation")):
            answer = (
                "Example equation: 2x + 4 = 10. Subtract 4 from both sides to get 2x = 6, "
                "then divide both sides by 2 to get x = 3. Check: 2(3) + 4 = 10.\n\n"
                "This is a fixed example, not a calculation of your specific question."
            )
        elif any(word in text for word in ("study", "exam", "revision")):
            answer = (
                "Try a 25-minute study session: choose one topic, recall what you know without notes, "
                "check gaps, then answer three practice questions. Take a short break and review tomorrow.\n\n"
                "Active recall and spaced practice are more useful than only rereading notes."
            )
        else:
            answer = (
                "This is the rule-based classroom demo, not a live AI model. Try asking about Python "
                "classes, SQLite databases, APIs, an algebra example, or exam study tips. "
                "Online mode can answer broader questions using your chosen external model."
            )
        return f"{OFFLINE_PREFIX}\n\n{answer}"
