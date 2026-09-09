"""Exercise real Flet controls through an in-process backend, with no network."""

import asyncio
from types import SimpleNamespace

import httpx
import pytest

from nexora.api.app import create_app
from nexora.ui.client import APIClient
from nexora.ui.state import UIState, response_text
from nexora.ui.workspace import Workspace


class PageStub:
    width, height = 1440, 900
    platform_brightness = None

    def __init__(self):
        self.controls, self.dialogs = [], []
        self.poll = None

    def add(self, *controls):
        self.controls.extend(controls)

    def update(self):
        pass

    def run_task(self, function):
        self.poll = function

    def show_dialog(self, dialog):
        self.dialogs.append(dialog)

    def pop_dialog(self):
        return self.dialogs.pop() if self.dialogs else None


@pytest.fixture
async def workspace(settings, monkeypatch):
    api = create_app(settings)
    real_client = httpx.AsyncClient

    def local_client(**kwargs):
        kwargs["transport"] = httpx.ASGITransport(app=api)
        return real_client(**kwargs)

    monkeypatch.setattr("nexora.ui.client.httpx.AsyncClient", local_client)
    async with api.router.lifespan_context(api):
        state = UIState(preference_path=None)
        state.preferences["welcomed"] = True
        ui = Workspace(PageStub(), state=state)
        await ui.start()
        yield ui, api.state.service


async def test_flet_controls_and_callbacks(workspace):
    ui, service = workspace
    ui.goal.value = "calculate 2 + 3"
    await ui.goal.on_submit(None)
    if service.running:
        await asyncio.gather(*list(service.running.values()))
    task = service.store.list()[0]
    await ui.load_task(task.id)
    assert task.status == "COMPLETED"
    assert "Result: 5" in response_text(ui.state.task)
    assert ui.page.poll is not None
    await ui.new_task()
    assert ui.state.task is None and ui.goal.value == ""
    await ui.open_handler(task.id)()
    assert ui.state.task["id"] == task.id


@pytest.mark.parametrize(
    "screen", ["Chat", "Projects", "Generated files", "Memory", "Tools", "Task history", "Settings"]
)
@pytest.mark.parametrize("width,height", [(1440, 900), (900, 650)])
async def test_navigation_and_responsive_controls(workspace, screen, width, height):
    ui, _ = workspace
    ui.page.width, ui.page.height = width, height
    await ui.navigate_handler(screen)()
    assert ui.state.screen == screen
    assert ui.root.content is not None


async def test_approval_dialog_reject_and_cancel(workspace):
    ui, service = workspace
    ui.goal.value = "approval demo"
    await ui.submit()
    assert ui.state.task["status"] == "AWAITING_APPROVAL"
    dialog = ui.page.dialogs[-1]
    assert dialog.modal
    await dialog.actions[1].on_click(None)
    assert service.store.list()[0].status == "BLOCKED"
    await ui.new_task()
    ui.goal.value = "approval demo"
    await ui.submit()
    await ui.page.dialogs[-1].actions[0].on_click(None)
    assert service.store.get(ui.state.task["id"]).status == "CANCELLED"


async def test_approval_dialog_approve(workspace):
    ui, service = workspace
    ui.goal.value = "approval demo"
    await ui.submit()
    await ui.page.dialogs[-1].actions[2].on_click(None)
    if service.running:
        await asyncio.gather(*list(service.running.values()))
    assert service.store.get(ui.state.task["id"]).status == "COMPLETED"


async def test_history_filters_and_appearance(workspace):
    ui, service = workspace
    service.create("calculate 12")
    service.create("list files")
    await ui.refresh()
    ui.state.search = "calculate"
    assert len(ui.state.filtered_tasks()) == 1
    await ui.toggle_theme()
    assert ui.state.preferences["theme"] == "dark"
    await ui.text_changed(SimpleNamespace(control=SimpleNamespace(value="18")))
    assert ui.goal.text_size == 18


async def test_offline_state():
    class Offline(APIClient):
        async def request(self, *args, **kwargs):
            raise httpx.ConnectError("offline")

    ui = Workspace(PageStub(), client=Offline(), state=UIState(preference_path=None))
    await ui.start()
    assert not ui.state.connected and "offline" in ui.error


async def test_public_settings_never_exposes_keys(workspace):
    ui, _ = workspace
    assert set(ui.state.settings) == {
        "provider",
        "safe_mode",
        "max_plan_steps",
        "max_tool_retries",
        "max_task_seconds",
        "workspace",
    }


def test_preferences_persist(tmp_path):
    path = tmp_path / "prefs.json"
    state = UIState(preference_path=path)
    state.preferences["theme"] = "dark"
    state.save_preferences()
    another = UIState(preference_path=path)
    another.load_preferences()
    assert another.preferences["theme"] == "dark"
