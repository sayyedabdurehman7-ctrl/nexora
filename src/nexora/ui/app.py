"""NEXORA Python-only application entry point."""

import flet as ft

from nexora.ui.conversation_workspace import ConversationWorkspace as Workspace


async def build(page: ft.Page) -> Workspace:
    workspace = Workspace(page)
    await workspace.start()
    return workspace


def main() -> None:
    ft.run(build)


if __name__ == "__main__":
    main()
