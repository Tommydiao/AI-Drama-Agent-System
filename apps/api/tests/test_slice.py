from fastapi.testclient import TestClient

from app.main import create_app
from app.repository import SqliteProjectRepository


def test_full_mock_story_to_rough_cut_mp4(tmp_path):
    repository = SqliteProjectRepository(tmp_path / "test.sqlite3")
    client = TestClient(create_app(repository, tmp_path / "storage"))
    created = client.post("/projects", json={"title": "门外的人", "premise": "深夜门外传来熟悉声音"})
    assert created.status_code == 201
    project_id = created.json()["id"]
    started = client.post(f"/projects/{project_id}/commands/start")
    assert started.status_code == 200
    body = started.json()
    assert body["production_state"] == "ROUGH_CUT_READY"
    media = client.get(f"/assets/{body['rough_cut_asset_id']}/content")
    assert media.status_code == 200
    assert media.headers["content-type"].startswith("video/mp4")
    assert len(media.content) > 10_000
