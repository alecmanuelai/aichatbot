"""Diagnose Gemini access without revealing credentials or saved conversations.

Run with the project's virtual environment: python check_online.py.
By default, only the model list is requested. --chat or --native-chat sends one
short test prompt using the configured model; this can consume API quota.
"""

import argparse
import re
from urllib.parse import urlsplit

import requests

from backend.ai_service import AIService, BearerAuth
from config import AppConfig, ConfigurationError

GEMINI_ROOT = "https://generativelanguage.googleapis.com/v1beta/openai"
GEMINI_NATIVE_ROOT = "https://generativelanguage.googleapis.com/v1beta"
CHAT_PROMPT = "Reply with exactly: StudyBuddy is online."
ERROR_STATUSES = frozenset({
    "INVALID_ARGUMENT", "FAILED_PRECONDITION", "OUT_OF_RANGE", "NOT_FOUND",
    "ALREADY_EXISTS", "PERMISSION_DENIED", "UNAUTHENTICATED", "RESOURCE_EXHAUSTED",
    "CANCELLED", "DATA_LOSS", "UNKNOWN", "INTERNAL", "UNAVAILABLE",
    "DEADLINE_EXCEEDED", "UNIMPLEMENTED", "ABORTED",
})
ERROR_REASONS = {
    "API_KEY_INVALID": "The API key is invalid. Create a replacement in Google AI Studio.",
    "API_KEY_EXPIRED": "The API key has expired. Create a replacement in Google AI Studio.",
    "API_KEY_SERVICE_BLOCKED": "The key's API restrictions block this service. Check its Gemini API access.",
    "API_KEY_HTTP_REFERRER_BLOCKED": "The key's website restrictions block this desktop request. Check its application restrictions.",
    "API_KEY_IP_ADDRESS_BLOCKED": "The key's IP restrictions block this connection. Check its application restrictions.",
    "SERVICE_DISABLED": "The Gemini API is disabled for this Google project. Check the project's API settings.",
    "BILLING_DISABLED": "Google requires billing for this request. Review the project's billing settings and pricing.",
    "CONSUMER_INVALID": "Google rejected the associated project. Check the key's project in AI Studio.",
}


class GeminiKeyAuth(requests.auth.AuthBase):
    """Send a Gemini API key in a header, without netrc or URL credentials."""

    def __init__(self, api_key: str):
        self._api_key = api_key

    def __call__(self, request):
        request.headers.pop("Authorization", None)
        request.headers["x-goog-api-key"] = self._api_key
        return request


def valid_gemini_config(config: AppConfig, report) -> bool:
    try:
        config.validate()
    except ConfigurationError as error:
        report(str(error))
        return False
    if config.mode != "online":
        report("Online mode is not selected. Set AI_MODE=online and run this check again.")
        return False
    url = urlsplit(config.base_url)
    if (url.hostname != "generativelanguage.googleapis.com"
            or url.port not in (None, 443)
            or url.path.rstrip("/") != "/v1beta/openai"):
        report(f"For Gemini, set AI_BASE_URL={GEMINI_ROOT}")
        return False
    return True


def check_connection(config: AppConfig, report=print) -> int:
    """Return zero for successful model access; a chat reply is still untested."""
    if not valid_gemini_config(config, report):
        return 1

    report("Checking Gemini model access. No chat-generation request is sent.")
    try:
        with requests.Session() as session:
            session.auth = BearerAuth(config.api_key)
            with session.get(
                config.base_url.rstrip("/") + "/models",
                timeout=(10, 20), verify=True, allow_redirects=False,
            ) as response:
                status = response.status_code
                report(f"HTTP status: {status}")
                if status in (401, 403):
                    report("Access was rejected. Check that your Google AI Studio key is active and allowed to use the Gemini API.")
                    return 1
                if status == 429:
                    report("Google reported a rate or quota limit. Check your project's limits in AI Studio.")
                    return 1
                if status in (408, 504):
                    report("The server reported a timeout. Wait before trying again.")
                    return 1
                if 300 <= status < 400:
                    report("A redirect was refused. Check the Gemini API root and any network sign-in page.")
                    return 1
                if status >= 500:
                    report("The server reported a service problem. Check Google's service status before retrying.")
                    return 1
                if status != 200:
                    report("The model-list request failed. Check the Gemini API root and project configuration.")
                    return 1
                try:
                    data = response.json()["data"]
                    if not isinstance(data, list) or not data:
                        raise ValueError
                    # Print only ordinary Gemini model identifiers, never arbitrary
                    # provider response text or a user-supplied configuration value.
                    model_ids = sorted({
                        model["id"].removeprefix("models/")
                        for model in data
                        if isinstance(model, dict)
                        and isinstance(model.get("id"), str)
                        and re.fullmatch(r"(?:models/)?gemini-[a-zA-Z0-9._-]{1,80}", model["id"])
                        and config.api_key not in model["id"]
                    })
                    if not model_ids:
                        raise ValueError
                except (ValueError, KeyError, TypeError):
                    report("The server returned an empty or unexpected model list. Its response body has not been printed.")
                    return 1
    except requests.ConnectTimeout:
        report("Connection timed out before reaching Gemini. Check your network, VPN/proxy, or firewall access to generativelanguage.googleapis.com.")
        return 1
    except requests.ReadTimeout:
        report("Reading the model list timed out. The delay also affects a request that generates no text; check your connection or try another network.")
        return 1
    except requests.exceptions.SSLError:
        report("TLS certificate verification failed. Check your computer clock and trusted certificate/proxy setup; keep verification enabled.")
        return 1
    except requests.exceptions.ProxyError:
        report("The configured network proxy could not reach Gemini. Check your proxy settings.")
        return 1
    except requests.Timeout:
        report("The model-list request timed out. Check network access to Gemini before retrying chat.")
        return 1
    except requests.RequestException:
        report("The model list could not be reached. Check DNS, network access, and the Gemini API root.")
        return 1

    report("Gemini model listing succeeded.")
    available = config.model.removeprefix("models/") in model_ids
    report("Configured model listed: " + ("yes" if available else "no"))
    flash_models = [model for model in model_ids if "flash" in model.lower()]
    report("Gemini Flash models returned:")
    for model in flash_models:
        report("  " + model)
    if not flash_models:
        report("  No Flash model identifiers were returned.")
    if not available:
        report("The configured model was not found in this response. Check AI_MODEL against your project's available models.")
    report("This check does not establish chat-generation access or quota. A real chat reply remains untested.")
    return 0 if available else 1


def report_chat_error(response, report) -> None:
    """Map provider errors to fixed text; never echo arbitrary response fields."""
    status = response.status_code
    explanations = {
        400: "Google rejected the test request. Check the safe error details below.",
        401: "Authentication was rejected. Check that your AI Studio key is active.",
        403: "Chat access was rejected. Check the key's restrictions and project permissions.",
        404: "The chat endpoint or selected model was not found. Check AI_MODEL and the API root.",
        408: "Google reported a timeout. Wait before trying again.",
        429: "A rate or quota limit was reached. Check the project's limits in AI Studio.",
        503: "Gemini reported that this request's service or model is temporarily unavailable.",
        504: "Google reported a timeout. Wait before trying again.",
    }
    if 300 <= status < 400:
        report("A redirect was refused. Check the API root and any network sign-in page.")
        return
    report(explanations.get(status, "Google did not accept the chat request."))
    try:
        data = response.json()
    except ValueError:
        report("No structured error details were returned. The response body was not printed.")
        return
    # Some Google endpoints wrap their error object in a list.
    entries = data if isinstance(data, list) else [data]
    for entry in entries:
        error = entry.get("error") if isinstance(entry, dict) else None
        if not isinstance(error, dict):
            continue
        error_status = error.get("status")
        if isinstance(error_status, str) and error_status in ERROR_STATUSES:
            report("Google error status: " + error_status)
        details = error.get("details", [])
        if isinstance(details, list):
            for detail in details:
                reason = detail.get("reason") if isinstance(detail, dict) else None
                if isinstance(reason, str) and reason in ERROR_REASONS:
                    report("Google error reason: " + reason)
                    report(ERROR_REASONS[reason])
        message = error.get("message")
        if not isinstance(message, str):
            continue
        message = message.lower()
        # Inspect messages only to select a fixed explanation. Keys, project IDs,
        # URLs, and arbitrary provider text must never appear in diagnostic output.
        if any(phrase in message for phrase in ("api key not valid", "invalid api key", "api key expired", "api key was reported as leaked")):
            report("Google rejected the API key. Create a replacement in Google AI Studio and update your private .env.")
        if "api keys are not supported" in message:
            report("Google says this request requires a different authentication method. Check the API endpoint and key type.")
        if "location is not supported" in message or "unsupported region" in message:
            report("Google reports that this service is unavailable in your current region. Check Gemini's supported regions.")
        if any(phrase in message for phrase in ("enable billing", "billing is required", "free tier is not available")):
            report("Google requires billing for this request. Review the project's billing settings and pricing before enabling it.")
        if "model" in message and any(phrase in message for phrase in ("not found", "not supported", "not available")):
            report("Google reports that the selected model is missing or unsupported for this request. Model listing alone does not establish chat support.")
        if "alternate" in message and ("role" in message or "user" in message):
            report("Google rejected the conversation's role ordering.")
    report("Raw provider error text was not printed.")


def check_chat(config: AppConfig, report=print, *, native=False) -> int:
    """Send one synthetic message through the selected Gemini API endpoint."""
    if not valid_gemini_config(config, report):
        return 1
    context = AIService.build_context([{"role": "user", "content": CHAT_PROMPT}])
    if native:
        model = config.model.removeprefix("models/")
        if not re.fullmatch(r"gemini-[a-zA-Z0-9._-]{1,80}", model):
            report("The native test requires a Gemini model ID, such as gemini-3.8-flash.")
            return 1
        endpoint = f"{GEMINI_NATIVE_ROOT}/models/{model}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": context[0]["content"]}]},
            "contents": [{"role": "user", "parts": [{"text": CHAT_PROMPT}]}],
        }
        auth = GeminiKeyAuth(config.api_key)
        report("API test: native Gemini generateContent (one request, no automatic fallback).")
    else:
        endpoint = config.endpoint
        payload = {"model": config.model, "messages": context}
        auth = BearerAuth(config.api_key)
        report("API test: Gemini OpenAI-compatible chat completions.")
    report("Sending one short Gemini test message. This can use API quota.")
    report("No saved conversations are read or sent.")
    try:
        with requests.Session() as session:
            session.auth = auth
            with session.post(
                endpoint, json=payload,
                timeout=(10, config.timeout_seconds), verify=True, allow_redirects=False,
            ) as response:
                report(f"HTTP status: {response.status_code}")
                if not 200 <= response.status_code < 300:
                    report_chat_error(response, report)
                    return 1
                try:
                    data = response.json()
                    if native:
                        parts = data["candidates"][0]["content"]["parts"]
                        if not isinstance(parts, list):
                            raise ValueError
                        content = "".join(
                            part["text"] for part in parts
                            if isinstance(part, dict) and not part.get("thought")
                            and isinstance(part.get("text"), str)
                        )
                    else:
                        content = data["choices"][0]["message"]["content"]
                    if not isinstance(content, str) or not content.strip():
                        raise ValueError
                except (ValueError, KeyError, IndexError, TypeError):
                    report("The chat response contained no usable text. Its body was not printed.")
                    return 1
    except requests.ConnectTimeout:
        report("Connection timed out before reaching Gemini. Check your network or proxy.")
        return 1
    except requests.ReadTimeout:
        report("Waiting for the chat reply timed out. No automatic retry was sent.")
        return 1
    except requests.exceptions.SSLError:
        report("TLS certificate verification failed. Check your clock and certificate setup; keep verification enabled.")
        return 1
    except requests.exceptions.ProxyError:
        report("The configured network proxy could not reach Gemini. Check your proxy settings.")
        return 1
    except requests.Timeout:
        report("The chat request timed out. No automatic retry was sent.")
        return 1
    except requests.RequestException:
        report("The chat request could not reach Gemini. Check DNS, network access, and the API root.")
        return 1
    if native:
        report("Native Gemini chat generation succeeded: a nonempty text reply was received.")
        report("This confirms one API reply using your local key. StudyBuddy still uses the compatibility endpoint until its integration is updated.")
    else:
        report("Chat generation succeeded: a nonempty text reply was received.")
        report("Open StudyBuddy, choose New Chat, and try a fresh question with these settings.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    chat_mode = parser.add_mutually_exclusive_group()
    chat_mode.add_argument("--chat", action="store_true", help="send one short compatibility API test message (can consume API quota)")
    chat_mode.add_argument("--native-chat", action="store_true", help="send one short native Gemini API test message (can consume API quota)")
    args = parser.parse_args(argv)
    try:
        config = AppConfig.load()
    except ConfigurationError as error:
        print(str(error))
        return 1
    except (OSError, UnicodeError):
        print("Could not read .env. Check its permissions and save it with UTF-8 encoding.")
        return 1
    if args.native_chat:
        return check_chat(config, native=True)
    return check_chat(config) if args.chat else check_connection(config)


if __name__ == "__main__":
    raise SystemExit(main())
