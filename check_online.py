"""Diagnose Gemini access without generating text or revealing credentials.

Run with the project's virtual environment: python check_online.py.
The only network operation is a verified HTTPS GET of Gemini's model list.
"""

import re
from urllib.parse import urlsplit

import requests

from backend.ai_service import BearerAuth
from config import AppConfig, ConfigurationError

GEMINI_ROOT = "https://generativelanguage.googleapis.com/v1beta/openai"


def check_connection(config: AppConfig, report=print) -> int:
    """Return zero for successful model access; a chat reply is still untested."""
    try:
        config.validate()
    except ConfigurationError as error:
        report(str(error))
        return 1
    if config.mode != "online":
        report("Online mode is not selected. Set AI_MODE=online and run this check again.")
        return 1
    url = urlsplit(config.base_url)
    if (url.hostname != "generativelanguage.googleapis.com"
            or url.port not in (None, 443)
            or url.path.rstrip("/") != "/v1beta/openai"):
        report(f"For Gemini, set AI_BASE_URL={GEMINI_ROOT}")
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


def main() -> int:
    try:
        config = AppConfig.load()
    except ConfigurationError as error:
        print(str(error))
        return 1
    except (OSError, UnicodeError):
        print("Could not read .env. Check its permissions and save it with UTF-8 encoding.")
        return 1
    return check_connection(config)


if __name__ == "__main__":
    raise SystemExit(main())
