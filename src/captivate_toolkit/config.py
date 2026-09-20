from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values

from .errors import ConfigError


@dataclass(frozen=True)
class Settings:
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    transcription_model: str = "whisper-1"
    vision_model: str = "gpt-4o-mini"
    text_model: str = "gpt-4o-mini"

    def require_ai(self) -> None:
        if not self.api_key:
            raise ConfigError("OPENAI_API_KEY harus diisi untuk fitur analisis AI.")
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ConfigError("OPENAI_BASE_URL harus berupa URL HTTP/HTTPS yang valid.")
        if parsed.username or parsed.password:
            raise ConfigError("OPENAI_BASE_URL tidak boleh menyimpan credential di URL.")
        for name, value in (
            ("TRANSCRIPTION_MODEL", self.transcription_model),
            ("VISION_MODEL", self.vision_model),
            ("TEXT_MODEL", self.text_model),
        ):
            if not value.strip():
                raise ConfigError(f"{name} harus diisi untuk fitur analisis AI.")


def load_settings(
    env_file: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
) -> Settings:
    """Load settings without mutating the process environment or logging secrets."""
    process = dict(os.environ if environ is None else environ)
    file_values: dict[str, str] = {}
    if env_file is not None:
        path = Path(env_file)
        if path.exists():
            file_values = {key: value or "" for key, value in dotenv_values(path).items() if key}

    def value(name: str, default: str = "") -> str:
        raw = process.get(name, file_values.get(name, default))
        return str(raw).strip() if raw is not None else default

    vision = value("VISION_MODEL", "gpt-4o-mini")
    return Settings(
        api_key=value("OPENAI_API_KEY"),
        base_url=value("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        transcription_model=value("TRANSCRIPTION_MODEL", "whisper-1"),
        vision_model=vision,
        text_model=value("TEXT_MODEL", vision),
    )
