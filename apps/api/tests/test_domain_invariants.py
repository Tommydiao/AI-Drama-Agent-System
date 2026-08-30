import pytest

from app.domain import (
    BudgetReservationState,
    Operation,
    OperationState,
    Shot,
    ShotProductionState,
    ShotVersion,
    ShotVersionStatus,
)


def test_shot_repair_counter_is_stable_across_version_replacement():
    shot = Shot(id="shot-1")
    first = ShotVersion(id="version-1", shot_id=shot.id, version_status=ShotVersionStatus.COMMITTED)
    shot.plan_repair()
    first.version_status = ShotVersionStatus.SUPERSEDED
    replacement = ShotVersion(id="version-2", shot_id=shot.id, version_status=ShotVersionStatus.COMMITTED)
    assert shot.creative_repair_count == 1
    assert shot.production_state is ShotProductionState.REPAIR_PLANNED
    assert replacement.version_status is ShotVersionStatus.COMMITTED


def test_second_repair_cap_waits_for_human_without_resetting_counter():
    shot = Shot(id="shot-1", creative_repair_count=2)
    shot.plan_repair()
    assert shot.creative_repair_count == 2
    assert shot.production_state is ShotProductionState.WAITING_HUMAN


def test_paid_operation_requires_independent_active_reservation():
    operation = Operation(id="operation-1", is_paid=True, reservation_state=BudgetReservationState.REQUESTED)
    with pytest.raises(ValueError, match="ACTIVE"):
        operation.authorize()
    operation.reservation_state = BudgetReservationState.ACTIVE
    operation.authorize()
    assert operation.state is OperationState.AUTHORIZED


def test_free_operation_requires_persisted_no_charge_fact_not_reservation():
    operation = Operation(id="operation-1", is_paid=False)
    with pytest.raises(ValueError, match="no-charge"):
        operation.authorize()
    operation.no_charge_policy_fact = True
    operation.authorize()
    assert operation.state is OperationState.AUTHORIZED
