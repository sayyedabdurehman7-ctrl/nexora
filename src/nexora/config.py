"""Validated configuration loaded from the NEXORA application directory."""

import os
import sys
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def application_dir() -> Path:
    """Return the launcher folder without depending on the process working directory."""
    configured = os.getenv("NEXORA_APP_DIR", "").strip().strip("\"'")
    if configured:
        return Path(configured).expanduser().resolve()
    if getattr(sys, "frozen", False):
        executable_dir = Path(sys.executable).resolve().parent
        return executable_dir.parent if executable_dir.name.lower() == "backend" else executable_dir
    return Path(__file__).resolve().parents[2]


APP_DIR = application_dir()
ENV_FILE = APP_DIR / ".env"

# Load the deterministic application-local file before Pydantic reads any settings.
load_dotenv(dotenv_path=ENV_FILE, override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore", hide_input_in_errors=True)

    nexora_env: str = "development"
    nexora_safe_mode: bool = True
    llm_provider: Literal["gemini", "mock"] = "mock"
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = ""
    voice_mode: Literal["off", "push_to_talk", "wake_word"] = "push_to_talk"
    assistant_voice_enabled: bool = False
    wake_phrase: str = "Hey NEXORA"
    stt_provider: Literal["faster_whisper"] = "faster_whisper"
    tts_provider: Literal["pyttsx3"] = "pyttsx3"
    voice_name: str = ""
    whisper_model: str = "tiny"
    max_recording_seconds: int = Field(default=60, ge=1, le=120)
    max_response_tokens: int = Field(default=1200, ge=64, le=4096)
    search_provider: Literal["mock"] = "mock"
    database_url: str = "sqlite:///data/nexora.db"
    nexora_workspace_dir: Path = Path("data/user_files")
    max_plan_steps: int = Field(default=10, ge=1, le=30)
    max_tool_retries: int = Field(default=2, ge=0, le=5)
    max_task_seconds: float = Field(default=180, gt=0, le=600)
    tool_timeout_seconds: float = Field(default=5, gt=0, le=30)

    @field_validator("gemini_api_key", mode="before")
    @classmethod
    def clean_gemini_key(cls, value):
        """Remove copy/paste whitespace and quote marks without exposing the secret."""
        if isinstance(value, SecretStr):
            value = value.get_secret_value()
        return str(value or "").strip().strip("\"'").strip()

    @field_validator("voice_mode", mode="before")
    @classmethod
    def migrate_voice_mode(cls, value):
        return "push_to_talk" if value == "basic" else value

    @model_validator(mode="after")
    def validate_supported(self):
        if not self.nexora_safe_mode:
            raise ValueError("Phase 1 requires NEXORA_SAFE_MODE=true")
        if not self.database_url.startswith("sqlite:///"):
            raise ValueError("DATABASE_URL must use local sqlite:///")
        return self


def load_settings(app_dir: Path | None = None) -> Settings:
    """Load settings from an absolute application-local .env path."""
    env_path = (app_dir or application_dir()).resolve() / ".env"
    load_dotenv(dotenv_path=env_path, override=False)
    return Settings(_env_file=env_path)


def gemini_key_diagnostic(settings: Settings | None = None) -> str:
    """Report key presence only; the secret value is never returned."""
    config = settings or load_settings()
    return "Gemini key detected" if config.gemini_api_key.get_secret_value() else "Gemini key not detected"
