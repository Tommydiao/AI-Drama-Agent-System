"""Canonical Phase-2 domain invariants, independent of a concrete database."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ShotProductionState(StrEnum):
    PLANNED = "PLANNED"
    KEYFRAME_IN_PROGRESS = "KEYFRAME_IN_PROGRESS"
    KEYFRAME_READY = "KEYFRAME_READY"
    CANDIDATE_GENERATING = "CANDIDATE_GENERATING"
    CANDIDATES_READY = "CANDIDATES_READY"
    QC_IN_PROGRESS = "QC_IN_PROGRESS"
    REPAIR_PLANNED = "REPAIR_PLANNED"
    WAITING_HUMAN = "WAITING_HUMAN"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ShotVersionStatus(StrEnum):
    DRAFT = "DRAFT"
    COMMITTED = "COMMITTED"
    INVALIDATED = "INVALIDATED"
    SUPERSEDED = "SUPERSEDED"


class OperationState(StrEnum):
    PLANNED = "PLANNED"
    AUTHORIZED = "AUTHORIZED"
    SUBMITTING = "SUBMITTING"
    SUBMISSION_UNKNOWN = "SUBMISSION_UNKNOWN"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class BudgetReservationState(StrEnum):
    REQUESTED = "REQUESTED"
    ACTIVE = "ACTIVE"
    SETTLING = "SETTLING"
    RELEASING = "RELEASING"
    SETTLED = "SETTLED"
    RELEASED = "RELEASED"


@dataclass
class Shot:
    id: str
    production_state: ShotProductionState = ShotProductionState.PLANNED
    creative_repair_count: int = 0

    def plan_repair(self) -> None:
        if self.creative_repair_count >= 2:
            self.production_state = ShotProductionState.WAITING_HUMAN
            return
        self.creative_repair_count += 1
        self.production_state = ShotProductionState.REPAIR_PLANNED


@dataclass
class ShotVersion:
    id: str
    shot_id: str
    version_status: ShotVersionStatus = ShotVersionStatus.DRAFT


@dataclass
class Operation:
    id: str
    state: OperationState = OperationState.PLANNED
    is_paid: bool = False
    reservation_state: BudgetReservationState | None = None
    no_charge_policy_fact: bool = False

    def authorize(self) -> None:
        if self.is_paid and self.reservation_state is not BudgetReservationState.ACTIVE:
            raise ValueError("Paid operation authorization requires an ACTIVE BudgetReservation")
        if not self.is_paid and not self.no_charge_policy_fact:
            raise ValueError("Free operation authorization requires a persisted no-charge policy fact")
        self.state = OperationState.AUTHORIZED

