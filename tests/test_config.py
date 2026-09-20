import os

import pytest

from captivate_toolkit.config import ConfigError, load_settings


def test_explicit_env_file_overrides_process_environment(tmp_path, monkeypatch):
    env_file = tmp_path / "settings.env"
    env_file.write_text(
        "OPENAI_BASE_URL=https://example.invalid/v1\nVISION_MODEL=file-vision\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("VISION_MODEL", "process-vision")

    settings = load_settings(env_file=env_file, environ=os.environ)

    assert settings.base_url == "https://example.invalid/v1"
    assert settings.vision_model == "process-vision"


def test_analysis_settings_require_key(tmp_path):
    settings = load_settings(env_file=tmp_path / "missing.env", environ={})

    with pytest.raises(ConfigError, match="OPENAI_API_KEY"):
        settings.require_ai()


def test_text_model_falls_back_to_vision_model():
    settings = load_settings(environ={"VISION_MODEL": "vision-model"})

    assert settings.text_model == "vision-model"
