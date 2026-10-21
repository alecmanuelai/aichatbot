"""Project-relative configuration, loaded without displaying secrets."""

from dataclasses import dataclass, field
import math
import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent
MAX_MESSAGE_LENGTH = 4000


class ConfigurationError(ValueError):
    """A safe configuration error suitable for the startup dialog."""


@dataclass(frozen=True)
class AppConfig:
    mode: str = "offline"
    base_url: str = ""
    api_key: str = field(default="", repr=False)
    model: str = ""
    timeout_seconds: float = 30.0

    @classmethod
    def load(cls, project_dir: Path = PROJECT_DIR) -> "AppConfig":
        load_dotenv(project_dir / ".env", override=False)
        try:
            timeout = float(os.getenv("AI_TIMEOUT_SECONDS", "30"))
        except ValueError:
            raise ConfigurationError("AI_TIMEOUT_SECONDS must be a number from 1 to 120.") from None
        config = cls(
            mode=os.getenv("AI_MODE", "offline").strip().lower(),
            base_url=os.getenv("AI_BASE_URL", "").strip(),
            api_key=os.getenv("AI_API_KEY", "").strip(),
            model=os.getenv("AI_MODEL", "").strip(),
            timeout_seconds=timeout,
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.mode not in {"offline", "online"}:
            raise ConfigurationError("AI_MODE must be offline or online.")
        if not math.isfinite(self.timeout_seconds) or not 1 <= self.timeout_seconds <= 120:
            raise ConfigurationError("AI_TIMEOUT_SECONDS must be a number from 1 to 120.")
        if self.mode == "offline":
            return
        if not all((self.base_url, self.api_key, self.model)):
            raise ConfigurationError("Online mode requires AI_BASE_URL, AI_API_KEY, and AI_MODEL in .env.")
        if self.api_key.startswith("replace_") or self.model.startswith("replace_"):
            raise ConfigurationError("Replace the online placeholders in your private .env file.")
        try:
            url = urlsplit(self.base_url)
            port = url.port
            valid = (
                url.scheme == "https" and bool(url.hostname)
                and url.username is None and url.password is None
                and "?" not in self.base_url and "#" not in self.base_url
                and not any(character.isspace() for character in self.base_url)
                and (port is None or port > 0)
            )
        except ValueError:
            valid = False
        if not valid:
            raise ConfigurationError("AI_BASE_URL must be an HTTPS API root without credentials, query, or fragment.")
        if self.base_url.rstrip("/").endswith("/chat/completions"):
            raise ConfigurationError("AI_BASE_URL is the API root; remove /chat/completions.")

    @property
    def endpoint(self) -> str:
        return self.base_url.rstrip("/") + "/chat/completions"
