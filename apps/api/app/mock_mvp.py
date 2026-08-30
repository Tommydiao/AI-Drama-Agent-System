"""Deterministic, database-agnostic Mock MVP application services.

These services model the Phase-4/5 behaviors independently from the temporary
Phase-1 SQLite project repository. They are intentionally small and replaceable
by the PostgreSQL/Temporal adapters planned for the next hardening phase.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from uuid import uuid4

from .domain import Operation, OperationState, Shot, ShotProductionState, ShotVersion, ShotVersionStatus


@dataclass
class MockAsset:
    id: str
    shot_id: str
    kind: str
    content_hash: str
    is_mock: bool = True


@dataclass
class MockShotRecord:
    shot: Shot
    committed_version: ShotVersion
    candidate_asset: MockAsset
    generated_asset_ids: list[str] = field(default_factory=list)


class MockProductionService:
    """In-memory application service used by Phase-4/5 tests and adapters."""

    def __init__(self, shot_count: int = 15) -> None:
        self.shot_count = shot_count
        self.shots: dict[str, MockShotRecord] = {}
        self.timeline_version = 1
        self.paused = False
        self.operations: dict[str, Operation] = {}
        self._operation_keys: dict[str, str] = {}
        self._lock = Lock()
        self.issues: list[dict] = []

    def seed(self) -> None:
        for position in range(1, self.shot_count + 1):
            shot_id = f"shot-{position}"
            asset = MockAsset(f"asset-{position}-v1", shot_id, "video", f"shot-{position}-stable")
            shot = Shot(shot_id, ShotProductionState.APPROVED)
            version = ShotVersion(f"version-{position}-v1", shot_id, ShotVersionStatus.COMMITTED)
            self.shots[shot_id] = MockShotRecord(shot, version, asset, [asset.id])

    def regenerate_shot(self, shot_id: str, *, spec_changed: bool = False, idempotency_key: str | None = None) -> dict:
        if self.paused:
            raise RuntimeError("Project is paused")
        record = self.shots[shot_id]
        operation = self._operation("REGENERATE_SHOT", idempotency_key or f"regen:{shot_id}:{len(record.generated_asset_ids)}", False)
        if operation.state is OperationState.SUCCEEDED:
            return {"operation_id": operation.id, "shot_id": shot_id, "asset_id": record.candidate_asset.id, "reused": True}
        if spec_changed:
            record.committed_version.version_status = ShotVersionStatus.SUPERSEDED
            record.committed_version = ShotVersion(f"{shot_id}-version-{len(record.generated_asset_ids) + 1}", shot_id, ShotVersionStatus.COMMITTED)
            record.shot.production_state = ShotProductionState.PLANNED
        candidate = MockAsset(f"{shot_id}-candidate-{len(record.generated_asset_ids) + 1}", shot_id, "video", f"{shot_id}:candidate:{len(record.generated_asset_ids) + 1}")
        record.candidate_asset = candidate
        record.generated_asset_ids.append(candidate.id)
        operation.state = OperationState.SUCCEEDED
        return {"operation_id": operation.id, "shot_id": shot_id, "asset_id": candidate.id, "reused": False}

    def replace_shot(self, shot_id: str, asset_id: str) -> dict:
        record = self.shots[shot_id]
        if asset_id not in record.generated_asset_ids:
            raise ValueError("Candidate does not belong to shot")
        record.candidate_asset = MockAsset(asset_id, shot_id, "video", f"published:{asset_id}")
        self.timeline_version += 1
        return {"timeline_version": self.timeline_version, "shot_id": shot_id, "asset_id": asset_id}

    def dialogue_impact_plan(self, line_id: str, shot_id: str) -> dict:
        return {"id": str(uuid4()), "line_id": line_id, "impacted_shot_ids": [shot_id], "impacted_asset_kinds": ["audio", "subtitle", "video"], "unaffected_shot_count": max(0, self.shot_count - 1)}

    def apply_dialogue_plan(self, plan: dict) -> dict:
        return {**plan, "status": "APPLIED", "timeline_version": self.timeline_version + 1}

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def repair(self, shot_id: str) -> dict:
        shot = self.shots[shot_id].shot
        shot.plan_repair()
        if shot.production_state is ShotProductionState.WAITING_HUMAN:
            issue = {"id": str(uuid4()), "shot_id": shot_id, "kind": "CREATIVE_REPAIR_LIMIT", "status": "OPEN"}
            self.issues.append(issue)
            return issue
        return {"shot_id": shot_id, "repair_count": shot.creative_repair_count, "state": shot.production_state}

    def _operation(self, kind: str, key: str, is_paid: bool) -> Operation:
        with self._lock:
            existing_id = self._operation_keys.get(key)
            if existing_id:
                return self.operations[existing_id]
            operation = Operation(str(uuid4()), is_paid=is_paid, no_charge_policy_fact=not is_paid)
            operation.authorize()
            operation.state = OperationState.RUNNING
            self._operation_keys[key] = operation.id
            self.operations[operation.id] = operation
            return operation


class ConcurrentBudget:
    def __init__(self, limit_minor: int) -> None:
        self.limit_minor = limit_minor
        self.reserved_minor = 0
        self._lock = Lock()

    def try_reserve(self, amount_minor: int) -> bool:
        with self._lock:
            if self.reserved_minor + amount_minor > self.limit_minor:
                return False
            self.reserved_minor += amount_minor
            return True

    def release(self, amount_minor: int) -> None:
        with self._lock:
            self.reserved_minor -= amount_minor


class SubmissionReconciler:
    def __init__(self) -> None:
        self.completed: set[str] = set()

    def mark_unknown(self, operation_id: str) -> str:
        return "SUBMISSION_UNKNOWN" if operation_id not in self.completed else "SUCCEEDED"

    def reconcile(self, operation_id: str) -> str:
        self.completed.add(operation_id)
        return "SUCCEEDED"

