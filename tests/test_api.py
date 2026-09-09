import time

from fastapi.testclient import TestClient

from nexora.api.app import create_app


def wait_task(client, task_id):
    for _ in range(100):
        task = client.get(f"/api/v1/tasks/{task_id}").json()
        if task["status"] in {"COMPLETED", "FAILED", "TIMED_OUT", "CANCELLED"}:
            return task
        time.sleep(0.01)
    raise AssertionError("Task did not finish")


def test_api_offline_vertical_slice(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json()["provider"] == "mock"
        created = client.post("/api/v1/tasks", json={"user_text": "calculate 3*7 then list files"})
        assert created.status_code == 201
        assert created.headers["X-Request-ID"]
        task_id = created.json()["id"]
        assert client.post(f"/api/v1/tasks/{task_id}/run").status_code == 200
        task = wait_task(client, task_id)
        assert task["status"] == "COMPLETED"
        assert task["plan"]["steps"][0]["result"]["data"]["value"] == 21
        assert client.get(f"/api/v1/tasks/{task_id}/events").json()
        assert len(client.get("/api/v1/tools").json()) == 2
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/tasks").json()[0]["id"] == task_id


def test_api_validation_and_origin(settings):
    with TestClient(create_app(settings)) as client:
        assert client.post("/api/v1/tasks", json={"user_text": ""}).status_code == 422
        assert client.get("/api/v1/tasks/missing").status_code == 404
        assert (
            client.post(
                "/api/v1/tasks",
                json={"user_text": "calculate 1"},
                headers={"Origin": "https://evil.example"},
            ).status_code
            == 403
        )
        response = client.post("/api/v1/tasks", json={"user_text": "calculate 1", "secret": "xyz"})
        assert "xyz" not in response.text


def test_api_approval_flow(settings):
    with TestClient(create_app(settings)) as client:
        task = client.post("/api/v1/tasks", json={"user_text": "approval demo"}).json()
        pending = client.post(f"/api/v1/tasks/{task['id']}/run").json()
        approval_id = pending["approval"]["id"]
        assert client.post(f"/api/v1/approvals/{approval_id}/approve").status_code == 200
        assert client.post(f"/api/v1/tasks/{task['id']}/run").status_code == 200
        assert wait_task(client, task["id"])["status"] == "COMPLETED"
