import asyncio

import pytest
from fastapi.testclient import TestClient

from nexora.api.app import create_app
from nexora.config import Settings
from nexora.providers import GeminiProvider, NexoraServiceProvider, ProviderError
from nexora.ui.pages.settings import settings as settings_page
from nexora.ui.theme import palette


def make_tester_settings(tmp_path):
    return Settings(
        _env_file=None,
        nexora_build_profile="tester",
        llm_provider="gemini",
        gemini_api_key="must-not-be-used",
        gemini_model="must-not-be-used",
        database_url=f"sqlite:///{(tmp_path / 'nexora.db').as_posix()}",
        nexora_workspace_dir=tmp_path / "workspace",
        nexora_data_dir=tmp_path,
    )


def test_tester_profile_forces_demo_and_removes_developer_routes(tmp_path):
    settings = make_tester_settings(tmp_path)
    assert settings.llm_provider == "mock"
    assert not settings.gemini_api_key.get_secret_value()
    with TestClient(create_app(settings)) as client:
        health = client.get("/health").json()
        assert health == {
            "status": "ok",
            "version": "0.3.1",
            "build_profile": "tester",
            "mode": "demo",
            "safe_mode": True,
        }
        public = client.get("/api/v1/settings").json()
        assert public["connection_status"] == "Demo mode"
        assert public["demo_mode"] is True
        assert not {"provider", "gemini_model", "gemini_key_status"} & public.keys()
        assert client.patch("/api/v1/settings/provider", json={"provider": "gemini"}).status_code == 404
        assert client.post("/api/v1/settings/gemini/test", json={"model": "x"}).status_code == 404


def test_tester_demo_handles_unicode_and_twenty_messages(tmp_path):
    with TestClient(create_app(make_tester_settings(tmp_path))) as client:
        chat_id = client.post("/api/v1/conversations").json()["id"]
        samples = ["Hello", "اردو پیغام", "हिंदी संदेश", "Working well 😊"]
        for index in range(20):
            response = client.post(
                f"/api/v1/conversations/{chat_id}/messages",
                json={"text": f"{samples[index % len(samples)]} {index}", "answer_mode": "medium"},
            )
            assert response.status_code == 200
            for _ in range(100):
                chat = client.get(f"/api/v1/conversations/{chat_id}").json()
                if chat["messages"][-1]["status"] != "responding":
                    break
                asyncio.run(asyncio.sleep(0.01))
            assert chat["messages"][-1]["status"] == "completed"
        assert len(chat["messages"]) == 40

        exported = client.post("/api/v1/data/export").json()
        export_path = tmp_path / "exports" / exported["filename"]
        assert "हिंदी संदेश" in export_path.read_text(encoding="utf-8")
        assert client.delete("/api/v1/data").status_code == 204
        assert client.get("/api/v1/conversations").json() == []


def test_tester_demo_answers_self_introduction(tmp_path):
    with TestClient(create_app(make_tester_settings(tmp_path))) as client:
        chat_id = client.post("/api/v1/conversations").json()["id"]
        response = client.post(
            f"/api/v1/conversations/{chat_id}/messages",
            json={"text": "give me self introduction", "answer_mode": "medium"},
        )
        assert response.status_code == 200
        answer = client.get(f"/api/v1/conversations/{chat_id}").json()["messages"][-1]["content"]
        assert answer.startswith("I am NEXORA, an autonomous multimodal personal AI workspace.")
        assert "I received your message" not in answer


def test_long_message_is_safe_in_demo_mode(tmp_path):
    with TestClient(create_app(make_tester_settings(tmp_path))) as client:
        chat_id = client.post("/api/v1/conversations").json()["id"]
        response = client.post(
            f"/api/v1/conversations/{chat_id}/messages",
            json={"text": "A" * 2000, "answer_mode": "light"},
        )
        assert response.status_code == 200


def test_tester_settings_control_tree_hides_developer_ai_controls():
    from types import SimpleNamespace

    app = SimpleNamespace(
        state=SimpleNamespace(settings={"build_profile": "tester", "demo_mode": True}),
        colors=palette(False),
        dark=False,
        pending_creator_website=None,
        navigate_handler=lambda screen: None,
        toggle_theme=None,
    )
    page = settings_page(app)
    controls = page.controls[0].controls
    visible_labels = {getattr(control, "value", "") for control in controls if control.visible}
    assert "Settings" in visible_labels
    assert "Tester Feedback" in visible_labels
    assert "Voice Settings" in visible_labels
    assert "AI Settings" not in visible_labels
    assert all(
        not (getattr(control, "visible", True) and getattr(control, "value", "") == "Gemini Model")
        for control in controls
    )


def test_unsupported_model_and_parameter_are_normalized():
    try:
        GeminiProvider("key", "bad model name")
    except ProviderError as exc:
        assert exc.status == "Invalid model"
    else:
        raise AssertionError("invalid model was accepted")

    error = RuntimeError("unexpected keyword argument: lexical unsupported")
    error.code = 400
    mapped = GeminiProvider.map_error(error)
    assert mapped.status == "Provider error"
    assert "does not support" in str(mapped)


class ServiceResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("service failure")

    def json(self):
        return self.payload


class FakeServiceClient:
    def __init__(self, failures=0):
        self.failures = failures
        self.calls = 0

    async def get(self, url, headers):
        return ServiceResponse({"status": "ok"})

    async def post(self, url, headers, json):
        self.calls += 1
        if self.calls <= self.failures:
            import httpx

            raise httpx.ConnectError("offline", request=httpx.Request("POST", url))
        assert json["answer_mode"] == "strong"
        assert headers["Authorization"].startswith("Bearer ")
        return ServiceResponse({"reply": "NEXORA online reply"})

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_secure_nexora_service_online_and_retry():
    client = FakeServiceClient(failures=1)
    provider = NexoraServiceProvider("https://service.example", "secret-token", client)
    assert (await provider.health_check())["mode"] == "online"
    reply = "".join(
        [part async for part in provider.stream_chat([{"role": "user", "content": "hi"}], "strong")]
    )
    assert reply == "NEXORA online reply"
    assert client.calls == 2
