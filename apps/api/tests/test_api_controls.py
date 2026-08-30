from fastapi.testclient import TestClient

from app.main import create_app
from app.repository import SqliteProjectRepository


def test_phase4_phase6_commands_are_exposed(tmp_path):
    client = TestClient(create_app(SqliteProjectRepository(tmp_path / "api.sqlite3"), tmp_path / "storage"))
    project = client.post("/projects", json={"title": "第二个故事", "premise": "雨夜的一封信"}).json()
    project_id = project["id"]
    started = client.post(f"/projects/{project_id}/commands/start")
    assert started.status_code == 200
    regen = client.post("/shots/shot-3/commands/regenerate", params={"project_id": project_id, "idempotency_key": "api-retry"})
    assert regen.status_code == 200
    repeat = client.post("/shots/shot-3/commands/regenerate", params={"project_id": project_id, "idempotency_key": "api-retry"})
    assert repeat.json()["operation_id"] == regen.json()["operation_id"]
    assert client.post(f"/projects/{project_id}/pause").json()["status"] == "PAUSED"
    assert client.post(f"/projects/{project_id}/resume").json()["status"] == "RUNNING"
    artifacts = client.get(f"/projects/{project_id}/artifacts")
    assert artifacts.status_code == 200
    assert artifacts.json()["screenplay"]["shot_count"] == 15
    assert client.get(f"/projects/{project_id}/costs").json()["is_mock"] is True
    assert client.get(f"/projects/{project_id}/evidence").json()["checks"]

