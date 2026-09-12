from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from nexora.api.app import create_app
from nexora.config import gemini_key_diagnostic, load_settings
from nexora.identity import NEXORA_IDENTITY_POLICY
from nexora.providers import FallbackProvider, GeminiProvider, ProviderError


class FakeModels:
    def __init__(self, chunks=None, error=None):
        self.chunks = chunks or []
        self.error = error
        self.call = None

    async def generate_content_stream(self, **kwargs):
        self.call = kwargs
        if self.error:
            raise self.error

        async def stream():
            for text in self.chunks:
                yield SimpleNamespace(text=text)

        return stream()


def fake_client(models):
    return SimpleNamespace(aio=SimpleNamespace(models=models))


@pytest.mark.asyncio
async def test_gemini_normal_stream_maps_multiturn_roles():
    models = FakeModels(["Hello", " again"])
    provider = GeminiProvider("fake-key", "fake-model", fake_client(models))
    messages = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
        {"role": "user", "content": "Continue"},
    ]
    result = "".join([part async for part in provider.stream_chat(messages)])
    assert result == "Hello again"
    assert [item["role"] for item in models.call["contents"]] == ["user", "model", "user"]
    assert models.call["model"] == "fake-model"
    assert "helpful answer" in models.call["config"]["system_instruction"]
    assert NEXORA_IDENTITY_POLICY in models.call["config"]["system_instruction"]


@pytest.mark.asyncio
async def test_gemini_missing_key_and_mock_fallback():
    provider = GeminiProvider("", "fake-model", fake_client(FakeModels()))
    with pytest.raises(ProviderError, match="GEMINI_API_KEY") as caught:
        _ = [part async for part in provider.stream_chat([{"role": "user", "content": "hi"}])]
    assert caught.value.status == "API key missing"

    fallback = FallbackProvider(provider)
    result = "".join([part async for part in fallback.stream_chat([{"role": "user", "content": "hi"}])])
    assert result.startswith("NEXORA's online service is not configured")


@pytest.mark.asyncio
async def test_gemini_quota_and_invalid_model_errors():
    quota = RuntimeError("RESOURCE_EXHAUSTED quota")
    quota.code = 429
    provider = GeminiProvider("fake-key", "fake-model", fake_client(FakeModels(error=quota)))
    with pytest.raises(ProviderError) as caught:
        _ = [part async for part in provider.stream_chat([{"role": "user", "content": "hi"}])]
    assert caught.value.status == "Quota limit reached"

    invalid = RuntimeError("model not found")
    invalid.code = 404
    mapped = GeminiProvider.map_error(invalid)
    assert mapped.status == "Provider error"
    assert "model" in str(mapped).lower()

    offline = GeminiProvider.map_error(ConnectionError("network offline"))
    assert offline.status == "Offline"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("Quota limit reached", "NEXORA's online service is temporarily at its limit"),
        (
            "Offline",
            "NEXORA cannot connect to its online service",
        ),
    ],
)
async def test_gemini_fallback_messages(status, expected):
    class FailedProvider:
        async def stream_chat(self, messages, answer_mode="medium"):
            raise ProviderError(status, "internal provider message")
            yield

        def classify_goal(self, goal):
            raise NotImplementedError

        def create_plan(self, goal):
            raise NotImplementedError

    provider = FallbackProvider(FailedProvider())
    result = "".join([part async for part in provider.stream_chat([{"role": "user", "content": "hi"}])])
    assert result.startswith(expected)


def test_gemini_selection_and_missing_key_status(settings):
    settings.gemini_model = "fake-model"
    with TestClient(create_app(settings)) as client:
        selected = client.patch(
            "/api/v1/settings/provider", json={"provider": "gemini", "gemini_model": "another-model"}
        )
        assert selected.status_code == 200
        assert selected.json()["provider"] == "gemini"
        assert selected.json()["gemini_key_status"] == "Not Configured"
        status = client.post("/api/v1/settings/gemini/test", json={"model": "another-model"}).json()
        assert status["status"] == "API key missing"
        assert status["message"] == "Gemini API key: Not configured"
        diagnostic = client.get("/api/v1/settings/gemini/diagnostic").json()
        assert diagnostic == {"message": "Gemini key not detected"}


@pytest.mark.asyncio
async def test_gemini_connected_status():
    provider = GeminiProvider("fake-key", "fake-model", fake_client(FakeModels(["OK"])))
    assert await provider.test_connection() == {
        "status": "Connected",
        "message": "Gemini API: Connected",
    }


@pytest.mark.asyncio
async def test_gemini_empty_response_is_normalized():
    provider = GeminiProvider("fake-key", "fake-model", fake_client(FakeModels([])))
    with pytest.raises(ProviderError, match="returned no text"):
        _ = [part async for part in provider.stream_chat([{"role": "user", "content": "hi"}])]


@pytest.mark.asyncio
async def test_gemini_network_timeout_retries_once():
    class RetryModels(FakeModels):
        def __init__(self):
            super().__init__(["Recovered"])
            self.calls = 0

        async def generate_content_stream(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError("network timeout")
            return await super().generate_content_stream(**kwargs)

    models = RetryModels()
    provider = GeminiProvider("fake-key", "fake-model", fake_client(models))
    result = "".join([part async for part in provider.stream_chat([{"role": "user", "content": "hi"}])])
    assert result == "Recovered"
    assert models.calls == 2


def test_absolute_env_loading_and_key_cleanup(tmp_path, monkeypatch):
    app_dir = tmp_path / "application"
    app_dir.mkdir()
    (app_dir / ".env").write_text(
        'LLM_PROVIDER=gemini\nGEMINI_API_KEY=  "fake-key"  \nGEMINI_MODEL=fake-model\n',
        encoding="utf-8",
    )
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    loaded = load_settings(app_dir)

    assert loaded.gemini_api_key.get_secret_value() == "fake-key"
    assert gemini_key_diagnostic(loaded) == "Gemini key detected"
    assert not hasattr(loaded, "api_key")


def test_missing_key_diagnostic(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    loaded = load_settings(tmp_path)
    assert gemini_key_diagnostic(loaded) == "Gemini key not detected"
