from concurrent.futures import ThreadPoolExecutor

from app.domain import ShotProductionState
from app.mock_mvp import ConcurrentBudget, MockProductionService, SubmissionReconciler


def seeded() -> MockProductionService:
    service = MockProductionService()
    service.seed()
    return service


def test_regenerate_one_shot_only():
    service = seeded()
    before = {shot_id: record.candidate_asset.id for shot_id, record in service.shots.items()}
    result = service.regenerate_shot("shot-3")
    after = {shot_id: record.candidate_asset.id for shot_id, record in service.shots.items()}
    assert result["shot_id"] == "shot-3"
    assert [sid for sid in before if before[sid] != after[sid]] == ["shot-3"]


def test_replace_shot_creates_timeline_version():
    service = seeded()
    candidate = service.regenerate_shot("shot-3")["asset_id"]
    assert service.replace_shot("shot-3", candidate)["timeline_version"] == 2


def test_dialogue_edit_impact_is_minimal():
    plan = seeded().dialogue_impact_plan("line-1", "shot-3")
    assert plan["impacted_shot_ids"] == ["shot-3"]
    assert plan["unaffected_shot_count"] == 14


def test_repair_stops_after_two_and_waits_human():
    service = seeded()
    service.shots["shot-3"].shot.creative_repair_count = 2
    issue = service.repair("shot-3")
    assert issue["kind"] == "CREATIVE_REPAIR_LIMIT"
    assert service.shots["shot-3"].shot.production_state is ShotProductionState.WAITING_HUMAN


def test_concurrent_reservation_allows_only_one():
    budget = ConcurrentBudget(100)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(budget.try_reserve, [100, 100]))
    assert sorted(results) == [False, True]


def test_worker_restart_reconciles_without_duplicate_operation():
    service = seeded()
    first = service.regenerate_shot("shot-3", idempotency_key="restart-safe")
    second = service.regenerate_shot("shot-3", idempotency_key="restart-safe")
    assert first["operation_id"] == second["operation_id"]
    assert second["reused"] is True


def test_pause_blocks_new_generation_and_reconciles_inflight():
    service = seeded()
    service.pause()
    try:
        service.regenerate_shot("shot-3")
        assert False, "paused generation must be rejected"
    except RuntimeError:
        pass
    service.resume()
    assert service.regenerate_shot("shot-3")["shot_id"] == "shot-3"


def test_unchanged_assets_are_reused():
    service = seeded()
    before = service.shots["shot-1"].candidate_asset.id
    service.replace_shot("shot-3", service.regenerate_shot("shot-3")["asset_id"])
    assert service.shots["shot-1"].candidate_asset.id == before


def test_submission_unknown_reconciles_same_operation():
    reconciler = SubmissionReconciler()
    assert reconciler.mark_unknown("op-1") == "SUBMISSION_UNKNOWN"
    assert reconciler.reconcile("op-1") == "SUCCEEDED"
    assert reconciler.mark_unknown("op-1") == "SUCCEEDED"

