import pytest

from nexora.config import Settings
from nexora.core import Service
from nexora.db import Store


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        llm_provider="mock",
        gemini_api_key="",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        nexora_workspace_dir=tmp_path / "files",
    )


@pytest.fixture
def service(settings):
    service = Service(settings, Store(settings.database_url))
    yield service
    service.store.engine.dispose()
