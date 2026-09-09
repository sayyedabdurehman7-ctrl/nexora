import pytest

from nexora.models import Status
from nexora.tools import MockResearch, PDFInput, ToolError


def test_memory_crud_and_disabled(service):
    item = service.store.memory_save("m1", "project", "NEXORA research question")
    assert item["enabled"] and service.store.memory_list()[0]["id"] == "m1"
    service.store.memory_save("m1", "project", "edited", enabled=False)
    assert service.store.memory_list() == []
    assert service.store.memory_list(include_disabled=True)[0]["content"] == "edited"
    service.store.memory_delete("m1")
    with pytest.raises(KeyError):
        service.store.memory_get("m1")


async def test_mock_research_has_evidence():
    tool = MockResearch()
    inputs = tool.input_model(query="agent safety")
    result = await tool.execute(inputs)
    assert result.success and result.data["sources"][0]["url"].startswith("mock://")
    assert await tool.verify(inputs, result)


async def test_pdf_requires_approved_path(service):
    with pytest.raises(ToolError) as error:
        await service.registry.get("pdf").execute(PDFInput(path="../secret.pdf"))
    assert error.value.code == "PATH_DENIED"


def test_phase2_planner_commands(service):
    research = service.create("research agent safety")
    assert research.status == Status.PLANNED
    assert research.plan.steps[0].selected_tool == "research"
    pdf = service.create("summarize pdf paper.pdf")
    assert pdf.status == Status.PLANNED
    assert pdf.plan.steps[0].selected_tool == "pdf"
