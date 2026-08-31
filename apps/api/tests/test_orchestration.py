from app.orchestration import build_project_request


def test_project_request_has_stable_unique_operation_ids():
    first = build_project_request("project-1", ["shot-1", "shot-2"])
    second = build_project_request("project-1", ["shot-1", "shot-2"])
    assert first == second
    assert first.shot_operations[0].operation_id != first.shot_operations[1].operation_id
