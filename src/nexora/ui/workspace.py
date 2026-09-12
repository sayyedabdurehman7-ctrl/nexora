"""Coordinate async UI events; task business logic stays in the API."""

import asyncio
import json

import flet as ft
import httpx

from nexora.ui.client import APIClient
from nexora.ui.components.approval_dialog import approval_dialog
from nexora.ui.components.sidebar import sidebar
from nexora.ui.components.task_panel import task_panel
from nexora.ui.pages.catalog import files, tools, unavailable
from nexora.ui.pages.chat import chat
from nexora.ui.pages.history import history
from nexora.ui.pages.settings import settings
from nexora.ui.state import TERMINAL, UIState
from nexora.ui.theme import PRIMARY, badge, coming, palette


class Workspace:
    def __init__(self, page: ft.Page, client: APIClient | None = None, state: UIState | None = None):
        self.page, self.client, self.state = page, client or APIClient(), state or UIState()
        self.state.load_preferences()
        self.root = ft.Container(expand=True)
        self.goal = ft.TextField(
            hint_text="Ask NEXORA anything or give it a goal...",
            multiline=True,
            shift_enter=True,
            min_lines=2,
            max_lines=4,
            border=ft.InputBorder.NONE,
            on_submit=self.submit,
            text_size=self.text_size,
        )
        self.shown_approvals: set[str] = set()
        self.disconnected = False
        self.error = ""

    @property
    def text_size(self) -> int:
        return int(self.state.preferences["text_size"])

    @property
    def dark(self) -> bool:
        return self.state.preferences["theme"] == "dark" or (
            self.state.preferences["theme"] == "system"
            and getattr(self.page, "platform_brightness", None) == ft.Brightness.DARK
        )

    @property
    def colors(self) -> dict:
        return palette(self.dark)

    async def start(self) -> None:
        self.page.title, self.page.padding, self.page.spacing = "NEXORA · Your AI workspace", 0, 0
        self.page.on_resize, self.page.on_disconnect = self.resize, self.disconnect
        self.page.add(self.root)
        self.state.busy = True
        self.render()
        await self.refresh()
        self.state.busy = False
        self.render()
        if not self.state.preferences["welcomed"]:
            await self.welcome_dialog()
        self.page.run_task(self.poll)

    def render(self) -> None:
        colors = self.colors
        self.page.bgcolor = colors["bg"]
        self.page.theme_mode = {
            "light": ft.ThemeMode.LIGHT,
            "dark": ft.ThemeMode.DARK,
            "system": ft.ThemeMode.SYSTEM,
        }[self.state.preferences["theme"]]
        self.page.theme = ft.Theme(color_scheme_seed=PRIMARY, font_family="Segoe UI")
        self.page.dark_theme = ft.Theme(color_scheme_seed=PRIMARY, font_family="Segoe UI")
        width, height = self.page.width or 1400, self.page.height or 900
        compact = self.state.collapsed or width < 1050 or height < 680
        modern = hasattr(self, "conversation")
        screen = self.state.screen
        title = (
            self.state.task["user_text"][:45] if self.state.task and self.state.screen == "Chat" else self.state.screen
        )
        if getattr(self, "conversation", None) and self.state.screen == "Chat":
            title = self.conversation["title"][:45]
        if modern:
            more_items = [
                ft.PopupMenuItem(
                    content=ft.Text("Back to chat" if screen != "Chat" else "Settings"),
                    icon=ft.Icons.CHAT_BUBBLE_OUTLINE if screen != "Chat" else ft.Icons.SETTINGS_OUTLINED,
                    on_click=self.navigate_handler("Chat" if screen != "Chat" else "Settings"),
                ),
                ft.PopupMenuItem(
                    content=ft.Text("Task history"),
                    icon=ft.Icons.HISTORY,
                    on_click=self.navigate_handler("Task history"),
                ),
                ft.PopupMenuItem(
                    content=ft.Text("Available tools"),
                    icon=ft.Icons.GRID_VIEW_ROUNDED,
                    on_click=self.navigate_handler("Tools"),
                ),
                ft.PopupMenuItem(
                    content=ft.Text("Use dark theme" if not self.dark else "Use light theme"),
                    icon=ft.Icons.DARK_MODE_OUTLINED if not self.dark else ft.Icons.LIGHT_MODE_OUTLINED,
                    on_click=self.toggle_theme,
                ),
                ft.PopupMenuItem(content=ft.Text("Quick guide"), icon=ft.Icons.HELP_OUTLINE, on_click=self.help_dialog),
                ft.PopupMenuItem(
                    content=ft.Text("Retry connection"),
                    icon=ft.Icons.REFRESH,
                    on_click=self.reconnect,
                ),
            ]
            if getattr(self, "conversation", None):
                more_items += [
                    ft.PopupMenuItem(
                        content=ft.Text("Rename chat"),
                        icon=ft.Icons.EDIT_OUTLINED,
                        on_click=self.rename_chat,
                    ),
                    ft.PopupMenuItem(
                        content=ft.Text("Delete chat"),
                        icon=ft.Icons.DELETE_OUTLINE,
                        on_click=self.delete_chat,
                    ),
                ]
            top = ft.Row(
                [
                    ft.Text(
                        title if title != "Chat" else "New conversation",
                        size=13,
                        weight=ft.FontWeight.W_600,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        expand=True,
                    ),
                    ft.TextButton(
                        "NEXORA Workspace",
                        icon=ft.Icons.SPACE_DASHBOARD_OUTLINED,
                        tooltip="Open plans and activity",
                        on_click=self.toggle_panel,
                    ) if screen == "Chat" else ft.Container(),
                    ft.PopupMenuButton(icon=ft.Icons.MORE_HORIZ, tooltip="More", items=more_items),
                ],
                spacing=8,
            )
        else:
            top = ft.Row(
                [
                    ft.Text(
                        title if title != "Chat" else "Your workspace",
                        size=17,
                        weight=ft.FontWeight.W_600,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        expand=True,
                    ),
                    badge("Safe Mode", "#268365"),
                    ft.IconButton(ft.Icons.DARK_MODE_OUTLINED, tooltip="Toggle theme", on_click=self.toggle_theme),
                    ft.IconButton(ft.Icons.VIEW_SIDEBAR_OUTLINED, tooltip="Show plan", on_click=self.toggle_panel),
                ]
            )
        if screen == "Chat":
            body = chat(self)
        elif screen == "Task history":
            body = history(self)
        elif screen == "Settings":
            body = settings(self)
        elif screen == "Tools":
            body = tools(self)
        elif screen == "Generated files":
            body = files(self)
        else:
            body = unavailable(self, screen)
        center_controls = [top, ft.Divider(color=colors["border"])]
        if self.error:
            center_controls.append(
                ft.Container(
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.ERROR_OUTLINE, color="#B4404A"),
                            ft.Text(self.error, expand=True, color="#B4404A", size=13),
                            ft.TextButton("View Details", on_click=self.show_error_details),
                            ft.TextButton("Retry", on_click=self.reconnect),
                        ]
                    ),
                    padding=10,
                    bgcolor=colors["accent"],
                    border_radius=10,
                )
            )
        if self.state.busy:
            center_controls.append(
                ft.Row(
                    [
                        ft.ProgressRing(width=16, height=16, stroke_width=2, color=PRIMARY),
                        ft.Text("NEXORA is thinking…", size=13, color=colors["muted"]),
                    ]
                )
            )
        center_controls.append(body)
        middle = ft.Container(
            ft.Column(center_controls, expand=True, spacing=12),
            expand=True,
            padding=14 if width < 900 or self.state.preferences["density"] == "Compact" else 20,
        )
        columns = [sidebar(self, compact), middle]
        if self.state.panel_open and width >= 1250 and screen == "Chat":
            columns.append(
                ft.Container(
                    task_panel(self),
                    width=320,
                    padding=16,
                    bgcolor=colors["surface"],
                    border=ft.Border.only(left=ft.BorderSide(1, colors["border"])),
                )
            )
        self.root.content = ft.Row(columns, expand=True, spacing=0, vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        self.page.update()

    async def refresh(self) -> None:
        try:
            tasks, registry, config = await asyncio.gather(
                self.client.request("GET", "/api/v1/tasks"),
                self.client.request("GET", "/api/v1/tools"),
                self.client.request("GET", "/api/v1/settings"),
            )
            self.state.tasks, self.state.tools, self.state.settings = tasks, registry, config
            self.state.connected, self.error = True, ""
        except (httpx.HTTPError, ValueError):
            self.state.connected = False
            self.error = "Backend offline or incompatible. Restart NEXORA with Open NEXORA.bat."

    async def reconnect(self, e=None) -> None:
        self.state.busy = True
        self.render()
        await self.refresh()
        self.state.busy = False
        self.render()
        if self.state.connected:
            self.notify("NEXORA is connected.")

    def notify(self, text: str) -> None:
        self.page.show_dialog(ft.SnackBar(ft.Text(text)))

    async def submit(self, e=None) -> None:
        text = (self.goal.value or "").strip()
        if self.state.busy or not text:
            if not text:
                self.notify("Enter a goal first. Try: calculate 2 + 3")
            return
        if self.state.task and self.state.task["status"] not in TERMINAL:
            self.notify("Stop or finish the current task before sending another goal.")
            return
        self.state.busy, self.state.screen, self.error = True, "Chat", ""
        self.render()
        try:
            task = await self.client.request("POST", "/api/v1/tasks", json={"user_text": text})
            self.state.task = task
            if task["status"] == "PLANNED":
                task = await self.client.request("POST", f"/api/v1/tasks/{task['id']}/run")
            self.goal.value = ""
            await self.load_task(task["id"])
            await self.refresh()
        except (httpx.HTTPError, ValueError) as exc:
            self.error = (
                str(exc) if isinstance(exc, ValueError) else "Connection lost. Your goal is still in the composer."
            )
        finally:
            self.state.busy = False
            self.render()

    async def load_task(self, task_id: str) -> None:
        task, events = await asyncio.gather(
            self.client.request("GET", f"/api/v1/tasks/{task_id}"),
            self.client.request("GET", f"/api/v1/tasks/{task_id}/events"),
        )
        self.state.task, self.state.events = task, events
        self.maybe_approve(task)

    def maybe_approve(self, task: dict) -> None:
        approval = task.get("approval")
        if approval and approval["status"] == "pending" and approval["id"] not in self.shown_approvals:
            self.shown_approvals.add(approval["id"])
            self.page.show_dialog(approval_dialog(self, task))

    async def decide(self, approval_id: str, approve: bool, task_id: str) -> None:
        try:
            await self.client.request("POST", f"/api/v1/approvals/{approval_id}/{'approve' if approve else 'reject'}")
            if approve:
                await self.client.request("POST", f"/api/v1/tasks/{task_id}/run")
            await self.load_task(task_id)
            self.notify("Action approved." if approve else "Action rejected. No action taken.")
        except (httpx.HTTPError, ValueError):
            self.shown_approvals.discard(approval_id)
            self.error = "Approval was not confirmed. Reconnect and reopen the task to check its status."
        self.render()

    async def stop_task(self, task_id: str) -> None:
        try:
            await self.client.request("POST", f"/api/v1/tasks/{task_id}/cancel")
            await self.load_task(task_id)
            self.notify("Stop requested. No further steps will start.")
        except (httpx.HTTPError, ValueError):
            self.error = "Could not confirm cancellation. Reconnect to check the task."
        self.render()

    async def stop(self, e=None) -> None:
        if self.state.task:
            await self.stop_task(self.state.task["id"])

    async def new_task(self, e=None) -> None:
        self.state.task, self.state.events, self.state.screen, self.goal.value = (
            None,
            [],
            "Chat",
            "",
        )
        self.render()

    def open_handler(self, task_id: str):
        async def open_task(e=None):
            try:
                self.state.screen = "Chat"
                await self.load_task(task_id)
            except (httpx.HTTPError, ValueError):
                self.error = "Could not load this task. Check the backend connection."
            self.render()

        return open_task

    def navigate_handler(self, screen: str):
        async def navigate(e=None):
            self.state.screen = screen
            self.render()

        return navigate

    def suggestion_handler(self, command: str):
        async def suggest(e=None):
            await self.new_task()
            self.goal.value = command
            self.render()
            await self.goal.focus()

        return suggest

    def retry_handler(self, task: dict):
        async def retry(e=None):
            await self.new_task()
            self.goal.value = task["user_text"]
            await self.submit()

        return retry

    def panel_tab_handler(self, tab: str):
        async def select(e=None):
            self.state.panel_tab = tab
            self.render()
            if (self.page.width or 1400) < 1250:
                self.page.pop_dialog()
                self.show_panel_dialog()

        return select

    async def open_plan(self, e=None) -> None:
        self.state.plan_expanded = True
        if (self.page.width or 1400) < 1250:
            self.show_panel_dialog()
        else:
            self.state.panel_open = True
            self.render()

    async def toggle_plan_steps(self, e=None) -> None:
        self.state.plan_expanded = not self.state.plan_expanded
        self.render()

    def decision_handler(self, approve: bool):
        async def decide(e=None):
            task = self.state.task
            approval = task.get("approval") if task else None
            if approval and approval.get("status") == "pending":
                await self.decide(approval["id"], approve, task["id"])

        return decide

    async def show_error_details(self, e=None) -> None:
        connection = "Connected" if self.state.connected else "Not connected"
        self.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Technical details"),
                content=ft.Text(
                    f"App connection: {connection}\n"
                    "No private message content or API keys are shown here.",
                    selectable=True,
                ),
                actions=[ft.TextButton("Close", on_click=lambda e: self.page.pop_dialog())],
            )
        )

    async def show_task_details(self, e=None) -> None:
        task = self.state.task
        if not task:
            return
        from nexora.ui.state import duration, simple_status

        details = [
            ft.Text(simple_status(task["status"]), weight=ft.FontWeight.W_600),
            ft.Text(f"Time: {duration(task)}"),
            ft.Divider(),
            ft.Text("Activity", weight=ft.FontWeight.W_600),
        ]
        details += [ft.Text(event["message"], size=13) for event in self.state.events[-12:]]
        if not self.state.events:
            details.append(ft.Text("No activity details yet."))
        self.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Task details"),
                content=ft.Container(
                    ft.Column(details, scroll=ft.ScrollMode.AUTO),
                    width=440,
                    height=min(430, (self.page.height or 800) - 220),
                ),
                actions=[ft.TextButton("Close", on_click=lambda e: self.page.pop_dialog())],
            )
        )

    def show_panel_dialog(self) -> None:
        self.page.show_dialog(
            ft.AlertDialog(
                content=ft.Container(
                    task_panel(self),
                    width=min(480, (self.page.width or 800) - 100),
                    height=min(600, (self.page.height or 800) - 150),
                )
            )
        )

    async def toggle_panel(self, e=None) -> None:
        if (self.page.width or 1400) < 1250:
            self.show_panel_dialog()
        else:
            self.state.panel_open = not self.state.panel_open
            self.render()

    async def toggle_sidebar(self, e=None) -> None:
        self.state.collapsed = not self.state.collapsed
        self.render()

    async def close_panel(self, e=None) -> None:
        if (self.page.width or 1400) < 1250:
            self.page.pop_dialog()
        else:
            self.state.panel_open = False
            self.render()

    async def search_changed(self, e) -> None:
        self.state.search = e.control.value or ""
        self.render()

    async def filter_status(self, e) -> None:
        self.state.status_filter = e.control.value
        self.render()

    async def filter_date(self, e) -> None:
        self.state.date_filter = e.control.value or ""
        self.render()

    async def toggle_theme(self, e=None) -> None:
        self.state.preferences["theme"] = "light" if self.dark else "dark"
        self.save_appearance()

    def save_appearance(self) -> None:
        try:
            self.state.save_preferences()
        except OSError:
            self.notify("Appearance changed for this session; preferences could not be saved.")
        self.goal.text_size = self.text_size
        self.render()

    async def theme_changed(self, e) -> None:
        self.state.preferences["theme"] = e.control.value
        self.save_appearance()

    async def density_changed(self, e) -> None:
        self.state.preferences["density"] = e.control.value
        self.save_appearance()

    async def text_changed(self, e) -> None:
        self.state.preferences["text_size"] = int(e.control.value)
        self.save_appearance()

    def copy_handler(self, text: str):
        async def copy(e=None):
            try:
                await ft.Clipboard().set(text)
                self.notify("Response copied.")
            except Exception:
                self.notify("Clipboard unavailable. Select the response text to copy it.")

        return copy

    async def source_link(self, e) -> None:
        self.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Link from task content"),
                content=ft.Text(str(e.data), selectable=True),
                actions=[ft.TextButton("Close", on_click=lambda e: self.page.pop_dialog())],
            )
        )

    async def help_dialog(self, e=None) -> None:
        self.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("A quick guide to NEXORA"),
                content=ft.Container(
                    ft.Column(
                        [
                            ft.Text("1. Start a New Task and type a supported goal."),
                            ft.Text("2. Press Enter or Run. Safe steps run automatically."),
                            ft.Text("3. Inspect Plan, Activity and Evidence in the task panel."),
                            ft.Text("4. Approve exact actions when asked, or choose Stop."),
                            ft.Text("Try: calculate 2 + 3\nlist files\nread notes.txt\napproval demo"),
                            ft.Text("Join with ' then '. Each goal is a separate saved task."),
                            ft.Text("Full guide: docs/SETUP.md in the NEXORA project folder."),
                        ],
                        tight=True,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    width=460,
                    height=min(360, (self.page.height or 800) - 230),
                ),
                actions=[ft.TextButton("Got it", on_click=lambda e: self.page.pop_dialog())],
            )
        )

    async def welcome_dialog(self, e=None) -> None:
        async def finish(e):
            self.state.preferences["welcomed"] = True
            self.save_appearance()
            self.page.pop_dialog()
            await self.new_task()
            self.goal.value = "calculate 2 + 3"
            self.render()

        self.page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Welcome to NEXORA"),
                content=ft.Container(
                    ft.Column(
                        [
                            ft.Text(
                                "Ask questions or give complete goals",
                                size=18,
                                weight=ft.FontWeight.W_600,
                            ),
                            ft.Text("NEXORA can run approved local commands safely."),
                            badge("1 · Safe local mode available"),
                            coming("Online AI setup"),
                            ft.Text("2 · Approved workspace", weight=ft.FontWeight.W_600),
                            ft.Text(
                                self.state.settings.get("workspace", "Connect to load this setting."),
                                selectable=True,
                            ),
                            coming("Choose folder"),
                            ft.Text(
                                "Edit NEXORA_WORKSPACE_DIR in .env and restart to change folders.",
                                size=12,
                            ),
                            badge("3 · Safe Mode confirmed on", "#268365"),
                            ft.Text("4 · Try your first goal: calculate 2 + 3"),
                        ],
                        tight=True,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    width=500,
                    height=min(460, (self.page.height or 800) - 230),
                ),
                actions=[ft.Button("Open my workspace", on_click=finish)],
            )
        )

    async def resize(self, e=None) -> None:
        self.render()

    async def disconnect(self, e=None) -> None:
        self.disconnected = True

    async def poll(self) -> None:
        last = ""
        while not self.disconnected:
            await asyncio.sleep(0.75)
            if not self.state.task or self.state.busy:
                continue
            task_id = self.state.task["id"]
            try:
                task = await self.client.request("GET", f"/api/v1/tasks/{task_id}")
                if not self.state.task or self.state.task["id"] != task_id:
                    continue
                snapshot = json.dumps(task, sort_keys=True)
                if snapshot != last:
                    await self.load_task(task_id)
                    await self.refresh()
                    self.render()
                last = snapshot
            except (httpx.HTTPError, ValueError):
                if self.state.connected:
                    self.state.connected = False
                    self.error = "Connection lost. Reconnect to check task status."
                    self.render()
