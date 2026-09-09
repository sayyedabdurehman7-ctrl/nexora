"""Validated configuration; no provider SDK belongs in the core."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    nexora_env: str = "development"
    nexora_safe_mode: bool = True
    llm_provider: Literal["mock", "openai", "ollama"] = "mock"
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = ""
    ollama_model: str = ""
    search_provider: Literal["mock"] = "mock"
    database_url: str = "sqlite:///data/nexora.db"
    nexora_workspace_dir: Path = Path("data/user_files")
    max_plan_steps: int = Field(default=10, ge=1, le=30)
    max_tool_retries: int = Field(default=2, ge=0, le=5)
    max_task_seconds: float = Field(default=180, gt=0, le=600)
    tool_timeout_seconds: float = Field(default=5, gt=0, le=30)

    @model_validator(mode="after")
    def validate_supported(self):
        if self.llm_provider == "openai" and (
            not self.openai_api_key.get_secret_value() or not self.openai_model
        ):
            raise ValueError("OpenAI requires OPENAI_API_KEY and OPENAI_MODEL in local .env")
        if self.llm_provider != "mock":
            raise ValueError("Phase 1 supports LLM_PROVIDER=mock only; cloud/local AI comes later")
        if not self.nexora_safe_mode:
            raise ValueError("Phase 1 requires NEXORA_SAFE_MODE=true")
        if not self.database_url.startswith("sqlite:///"):
            raise ValueError("DATABASE_URL must use local sqlite:///")
        return self
